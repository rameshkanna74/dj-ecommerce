#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3>=1.35"]
# ///
"""Deploy CoreCart (Django API + React SPA) to AWS at the lowest sensible cost.

Architecture (one region, default us-east-1):

    Browser --HTTPS--> CloudFront (free TLS + *.cloudfront.net URL, caching, security headers)
                          |  HTTP, only from CloudFront IPs (security group) + secret origin header (nginx)
                          v
                EC2 t4g.micro (Amazon Linux 2023, arm64, encrypted gp3, IMDSv2, no SSH, no key pair)
                  nginx -> React build + /static + /media, proxies /api and the admin to gunicorn
                  gunicorn (systemd, sandboxed) -> PostgreSQL (unix socket, peer auth) + Redis (loopback)
                S3 (private, encrypted): release bundles, nightly DB/media backups, Run Command logs
                SSM Parameter Store (SecureString): Django env + secrets.  Shell access: SSM Session Manager.

Credentials come from the normal boto3 chain (AWS_PROFILE / ~/.aws/credentials / env vars).

    uv run deploy/aws/deploy.py up          # create/update everything and deploy the current working tree
    uv run deploy/aws/deploy.py deploy      # code-only release (build frontend, upload, migrate, restart)
    uv run deploy/aws/deploy.py seed        # demo data + an admin account (credentials stored in SSM)
    uv run deploy/aws/deploy.py status
    uv run deploy/aws/deploy.py domain shop.example.com [www.shop.example.com]
    uv run deploy/aws/deploy.py stop | start
    uv run deploy/aws/deploy.py destroy --yes [--delete-bucket]

`python3 deploy/aws/deploy.py ...` works too if boto3 is installed.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover
    sys.exit("boto3 is required: `uv run deploy/aws/deploy.py ...` or `pip install boto3`.")

ROOT = Path(__file__).resolve().parents[2]
NAME = "corecart"
PARAM = "/corecart"
COMMENT = "corecart"  # CloudFront distribution marker
TAG = {"Key": "Project", "Value": NAME}
AMI_PARAM = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
CF_PREFIX_LIST = "com.amazonaws.global.cloudfront.origin-facing"
ROOT_VOLUME_GB = 16
# Never shipped to the server.
EXCLUDE_PREFIXES = (".claude/", ".git/", ".venv/", "frontend/node_modules/", "media/", "staticfiles/", "aws.md")


def log(msg: str) -> None:
    print(f"==> {msg}", flush=True)


class Deployer:
    def __init__(self, region: str, profile: str | None):
        self.region = region
        self.s = boto3.Session(region_name=region, profile_name=profile)
        self.ec2 = self.s.client("ec2")
        self.iam = self.s.client("iam")
        self.s3 = self.s.client("s3")
        self.ssm = self.s.client("ssm")
        self.cf = self.s.client("cloudfront")
        self.acm = self.s.client("acm", region_name="us-east-1")  # CloudFront certs live in us-east-1
        self.account = self.s.client("sts").get_caller_identity()["Account"]
        self.bucket = f"{NAME}-{self.account}-{region}"

    # ------------------------------------------------------------------ SSM params
    def get_param(self, name: str) -> str | None:
        try:
            return self.ssm.get_parameter(Name=f"{PARAM}/{name}", WithDecryption=True)["Parameter"]["Value"]
        except self.ssm.exceptions.ParameterNotFound:
            return None

    def put_param(self, name: str, value: str, secure: bool = True) -> None:
        self.ssm.put_parameter(Name=f"{PARAM}/{name}", Value=value, Overwrite=True,
                               Type="SecureString" if secure else "String", Tier="Standard")

    # ------------------------------------------------------------------ S3
    def ensure_bucket(self) -> None:
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except ClientError:
            log(f"creating S3 bucket {self.bucket}")
            kwargs = {} if self.region == "us-east-1" else {
                "CreateBucketConfiguration": {"LocationConstraint": self.region}}
            self.s3.create_bucket(Bucket=self.bucket, **kwargs)
            self.s3.get_waiter("bucket_exists").wait(Bucket=self.bucket)
        self.s3.put_public_access_block(Bucket=self.bucket, PublicAccessBlockConfiguration={
            "BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True})
        self.s3.put_bucket_encryption(Bucket=self.bucket, ServerSideEncryptionConfiguration={"Rules": [
            {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}, "BucketKeyEnabled": True}]})
        self.s3.put_bucket_policy(Bucket=self.bucket, Policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
                "Resource": [f"arn:aws:s3:::{self.bucket}", f"arn:aws:s3:::{self.bucket}/*"],
                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
            }],
        }))

        def expire(rule_id, prefix, days):
            return {"ID": rule_id, "Status": "Enabled", "Filter": {"Prefix": prefix},
                    "Expiration": {"Days": days}}
        self.s3.put_bucket_lifecycle_configuration(Bucket=self.bucket, LifecycleConfiguration={"Rules": [
            expire("releases", "releases/", 14),
            expire("ssm-output", "ssm-output/", 7),
            expire("db-backups", "backups/db/", 14),
            {"ID": "abort-mpu", "Status": "Enabled", "Filter": {"Prefix": ""},
             "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1}},
        ]})
        self.s3.put_bucket_tagging(Bucket=self.bucket, Tagging={"TagSet": [TAG]})

    # ------------------------------------------------------------------ IAM
    def ensure_role(self) -> str:
        role = f"{NAME}-ec2"
        trust = {"Version": "2012-10-17", "Statement": [{
            "Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
        created = False
        try:
            self.iam.get_role(RoleName=role)
        except self.iam.exceptions.NoSuchEntityException:
            log(f"creating IAM role {role}")
            self.iam.create_role(RoleName=role, AssumeRolePolicyDocument=json.dumps(trust),
                                 Description="CoreCart web instance", Tags=[TAG])
            created = True
        self.iam.attach_role_policy(RoleName=role,
                                    PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore")
        b = f"arn:aws:s3:::{self.bucket}"
        self.iam.put_role_policy(RoleName=role, PolicyName=f"{NAME}-least-privilege", PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {"Sid": "ReadConfig", "Effect": "Allow", "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                 "Resource": f"arn:aws:ssm:{self.region}:{self.account}:parameter{PARAM}/*"},
                {"Sid": "ReadReleases", "Effect": "Allow", "Action": "s3:GetObject",
                 "Resource": f"{b}/releases/*"},
                {"Sid": "WriteBackupsAndLogs", "Effect": "Allow", "Action": ["s3:PutObject", "s3:PutObjectAcl"],
                 "Resource": [f"{b}/backups/*", f"{b}/ssm-output/*"]},
                {"Sid": "BucketMeta", "Effect": "Allow", "Action": "s3:GetEncryptionConfiguration", "Resource": b},
                {"Sid": "ListBackups", "Effect": "Allow", "Action": "s3:ListBucket", "Resource": b,
                 "Condition": {"StringLike": {"s3:prefix": ["backups/*"]}}},
            ],
        }))
        try:
            self.iam.get_instance_profile(InstanceProfileName=role)
        except self.iam.exceptions.NoSuchEntityException:
            self.iam.create_instance_profile(InstanceProfileName=role, Tags=[TAG])
            created = True
        profile = self.iam.get_instance_profile(InstanceProfileName=role)["InstanceProfile"]
        if not any(r["RoleName"] == role for r in profile["Roles"]):
            self.iam.add_role_to_instance_profile(InstanceProfileName=role, RoleName=role)
            created = True
        if created:
            time.sleep(15)  # IAM is eventually consistent
        return role

    # ------------------------------------------------------------------ network
    def default_vpc(self) -> str:
        vpcs = self.ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
        if not vpcs:
            sys.exit("No default VPC in this region. Create one: `aws ec2 create-default-vpc`.")
        return vpcs[0]["VpcId"]

    def pick_subnet(self, vpc: str, instance_type: str) -> str:
        offered = {o["Location"] for o in self.ec2.describe_instance_type_offerings(
            LocationType="availability-zone",
            Filters=[{"Name": "instance-type", "Values": [instance_type]}])["InstanceTypeOfferings"]}
        subnets = self.ec2.describe_subnets(Filters=[
            {"Name": "vpc-id", "Values": [vpc]}, {"Name": "default-for-az", "Values": ["true"]}])["Subnets"]
        for sn in sorted(subnets, key=lambda s: s["AvailabilityZone"]):
            if sn["AvailabilityZone"] in offered:
                return sn["SubnetId"]
        sys.exit(f"No default subnet offers {instance_type}.")

    def ensure_security_group(self, vpc: str) -> str:
        name = f"{NAME}-web"
        found = self.ec2.describe_security_groups(Filters=[
            {"Name": "group-name", "Values": [name]}, {"Name": "vpc-id", "Values": [vpc]}])["SecurityGroups"]
        if found:
            sg = found[0]["GroupId"]
        else:
            log("creating security group (HTTP from CloudFront only, no SSH)")
            sg = self.ec2.create_security_group(
                GroupName=name, VpcId=vpc, Description="CoreCart web: HTTP from CloudFront only",
                TagSpecifications=[{"ResourceType": "security-group", "Tags": [TAG, {"Key": "Name", "Value": name}]}],
            )["GroupId"]
        pl = self.ec2.describe_managed_prefix_lists(
            Filters=[{"Name": "prefix-list-name", "Values": [CF_PREFIX_LIST]}])["PrefixLists"][0]["PrefixListId"]
        try:
            self.ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[{
                "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
                "PrefixListIds": [{"PrefixListId": pl, "Description": "CloudFront origin-facing"}]}])
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidPermission.Duplicate":
                raise
        return sg

    # ------------------------------------------------------------------ EC2
    def find_instance(self) -> dict | None:
        res = self.ec2.describe_instances(Filters=[
            {"Name": "tag:Name", "Values": [f"{NAME}-web"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}])
        items = [i for r in res["Reservations"] for i in r["Instances"]]
        return items[0] if items else None

    def ensure_instance(self, instance_type: str) -> dict:
        inst = self.find_instance()
        if inst:
            if inst["State"]["Name"] in ("stopped", "stopping"):
                log("starting stopped instance")
                self.ec2.get_waiter("instance_stopped").wait(InstanceIds=[inst["InstanceId"]])
                self.ec2.start_instances(InstanceIds=[inst["InstanceId"]])
            self.ec2.get_waiter("instance_running").wait(InstanceIds=[inst["InstanceId"]])
            return self.find_instance()
        vpc = self.default_vpc()
        sg = self.ensure_security_group(vpc)
        subnet = self.pick_subnet(vpc, instance_type)
        profile = self.ensure_role()
        ami = self.ssm.get_parameter(Name=AMI_PARAM)["Parameter"]["Value"]
        log(f"launching {instance_type} ({ami})")
        for attempt in range(10):
            try:
                inst = self.ec2.run_instances(
                    ImageId=ami, InstanceType=instance_type, MinCount=1, MaxCount=1,
                    SubnetId=subnet, SecurityGroupIds=[sg],
                    IamInstanceProfile={"Name": profile},
                    MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled",
                                     "HttpPutResponseHopLimit": 1},
                    BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {
                        "VolumeSize": ROOT_VOLUME_GB, "VolumeType": "gp3", "Encrypted": True,
                        "DeleteOnTermination": True}}],
                    CreditSpecification={"CpuCredits": "standard"},  # never pay for burst credits
                    DisableApiTermination=True,
                    Monitoring={"Enabled": False},
                    TagSpecifications=[
                        {"ResourceType": "instance", "Tags": [TAG, {"Key": "Name", "Value": f"{NAME}-web"}]},
                        {"ResourceType": "volume", "Tags": [TAG, {"Key": "Name", "Value": f"{NAME}-web"}]}],
                )["Instances"][0]
                break
            except ClientError as e:
                if "instance profile" in str(e).lower() and attempt < 9:
                    time.sleep(6)
                    continue
                raise
        self.ec2.get_waiter("instance_running").wait(InstanceIds=[inst["InstanceId"]])
        return self.find_instance()

    def ensure_eip(self, instance_id: str) -> tuple[str, str]:
        addrs = self.ec2.describe_addresses(Filters=[{"Name": "tag:Project", "Values": [NAME]}])["Addresses"]
        if addrs:
            addr = addrs[0]
        else:
            log("allocating Elastic IP (stable origin address across stop/start)")
            addr = self.ec2.allocate_address(Domain="vpc", TagSpecifications=[
                {"ResourceType": "elastic-ip", "Tags": [TAG, {"Key": "Name", "Value": f"{NAME}-web"}]}])
        if addr.get("InstanceId") != instance_id:
            self.ec2.associate_address(AllocationId=addr["AllocationId"], InstanceId=instance_id)
        ip = addr["PublicIp"]
        for _ in range(30):
            dns = self.find_instance().get("PublicDnsName", "")
            if ip.replace(".", "-") in dns:
                return ip, dns
            time.sleep(2)
        sys.exit("Instance public DNS name did not update to the Elastic IP.")

    def wait_ssm(self, instance_id: str) -> None:
        log("waiting for the SSM agent to come online")
        for _ in range(90):
            info = self.ssm.describe_instance_information(
                Filters=[{"Key": "InstanceIds", "Values": [instance_id]}])["InstanceInformationList"]
            if info and info[0]["PingStatus"] == "Online":
                return
            time.sleep(10)
        sys.exit("SSM agent never came online (check the instance role and outbound internet).")

    def run(self, instance_id: str, script: str, comment: str, timeout: int = 3600) -> str:
        cmd = self.ssm.send_command(
            InstanceIds=[instance_id], DocumentName="AWS-RunShellScript", Comment=comment[:100],
            Parameters={"commands": [script], "executionTimeout": [str(timeout)]},
            OutputS3BucketName=self.bucket, OutputS3KeyPrefix="ssm-output",
        )["Command"]["CommandId"]
        log(f"{comment} (SSM command {cmd})")
        while True:
            time.sleep(5)
            try:
                inv = self.ssm.get_command_invocation(CommandId=cmd, InstanceId=instance_id)
            except self.ssm.exceptions.InvocationDoesNotExist:
                continue
            if inv["Status"] in ("Pending", "InProgress", "Delayed"):
                continue
            out, err = inv["StandardOutputContent"], inv["StandardErrorContent"]
            if out.strip():
                print(out.rstrip())
            if inv["Status"] != "Success":
                print(err.rstrip(), file=sys.stderr)
                sys.exit(f"Remote command failed ({inv['Status']}). Full log: "
                         f"s3://{self.bucket}/ssm-output/{cmd}/")
            return out

    # ------------------------------------------------------------------ CloudFront
    def _managed(self, kind: str, name: str) -> str:
        if kind == "cache":
            items = self.cf.list_cache_policies(Type="managed")["CachePolicyList"]["Items"]
            return next(i["CachePolicy"]["Id"] for i in items
                        if i["CachePolicy"]["CachePolicyConfig"]["Name"] == name)
        if kind == "origin":
            items = self.cf.list_origin_request_policies(Type="managed")["OriginRequestPolicyList"]["Items"]
            return next(i["OriginRequestPolicy"]["Id"] for i in items
                        if i["OriginRequestPolicy"]["OriginRequestPolicyConfig"]["Name"] == name)
        items = self.cf.list_response_headers_policies(Type="managed")["ResponseHeadersPolicyList"]["Items"]
        return next(i["ResponseHeadersPolicy"]["Id"] for i in items
                    if i["ResponseHeadersPolicy"]["ResponseHeadersPolicyConfig"]["Name"] == name)

    def find_distribution(self) -> dict | None:
        for page in self.cf.get_paginator("list_distributions").paginate():
            for d in page["DistributionList"].get("Items", []):
                if d["Comment"] == COMMENT:
                    return d
        return None

    def ensure_distribution(self, origin_dns: str, admin_url: str, origin_secret: str) -> dict:
        dist = self.find_distribution()
        if dist:
            return dist
        log("creating CloudFront distribution")
        optimized = self._managed("cache", "Managed-CachingOptimized")
        disabled = self._managed("cache", "Managed-CachingDisabled")
        all_viewer = self._managed("origin", "Managed-AllViewer")
        security = self._managed("headers", "Managed-SecurityHeadersPolicy")
        read = {"Quantity": 2, "Items": ["GET", "HEAD"], "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]}}

        def behavior(path: str | None, dynamic: bool) -> dict:
            b = {
                "TargetOriginId": "ec2", "ViewerProtocolPolicy": "redirect-to-https", "Compress": True,
                "ResponseHeadersPolicyId": security,
                "CachePolicyId": disabled if dynamic else optimized,
                "AllowedMethods": {
                    "Quantity": 7, "Items": ["GET", "HEAD", "OPTIONS", "PUT", "PATCH", "POST", "DELETE"],
                    "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                } if dynamic else read,
            }
            if dynamic:
                b["OriginRequestPolicyId"] = all_viewer  # cookies, query strings, Host, Authorization
            if path:
                b["PathPattern"] = path
            return b

        behaviors = [behavior("/api/*", True), behavior(f"/{admin_url.strip('/')}/*", True),
                     behavior("/static/*", False), behavior("/media/*", False), behavior("/assets/*", False)]
        config = {
            "CallerReference": f"{NAME}-{int(time.time())}",
            "Comment": COMMENT, "Enabled": True,
            "PriceClass": "PriceClass_100",  # cheapest edge set (North America + Europe)
            "HttpVersion": "http2and3", "IsIPV6Enabled": True,
            "Origins": {"Quantity": 1, "Items": [{
                "Id": "ec2", "DomainName": origin_dns,
                "CustomHeaders": {"Quantity": 1, "Items": [
                    {"HeaderName": "X-Origin-Verify", "HeaderValue": origin_secret}]},
                "CustomOriginConfig": {
                    "HTTPPort": 80, "HTTPSPort": 443, "OriginProtocolPolicy": "http-only",
                    "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                    "OriginReadTimeout": 30, "OriginKeepaliveTimeout": 5},
                "ConnectionAttempts": 3, "ConnectionTimeout": 10,
            }]},
            "DefaultCacheBehavior": behavior(None, False),  # the React SPA
            "CacheBehaviors": {"Quantity": len(behaviors), "Items": behaviors},
            "ViewerCertificate": {"CloudFrontDefaultCertificate": True},
            "Restrictions": {"GeoRestriction": {"RestrictionType": "none", "Quantity": 0}},
        }
        dist = self.cf.create_distribution_with_tags(DistributionConfigWithTags={
            "DistributionConfig": config, "Tags": {"Items": [TAG]}})["Distribution"]
        return {"Id": dist["Id"], "DomainName": dist["DomainName"], "Aliases": {"Quantity": 0}}

    def update_origin_dns(self, dist_id: str, origin_dns: str) -> None:
        resp = self.cf.get_distribution_config(Id=dist_id)
        cfg = resp["DistributionConfig"]
        if cfg["Origins"]["Items"][0]["DomainName"] != origin_dns:
            log("pointing CloudFront at the instance's current address")
            cfg["Origins"]["Items"][0]["DomainName"] = origin_dns
            self.cf.update_distribution(Id=dist_id, IfMatch=resp["ETag"], DistributionConfig=cfg)

    # ------------------------------------------------------------------ app config
    def hosts(self, dist: dict) -> tuple[list[str], str]:
        aliases = dist.get("Aliases", {}).get("Items", []) or []
        hosts = [*aliases, dist["DomainName"]]
        return hosts, f"https://{hosts[0]}"

    def write_env(self, dist: dict) -> dict:
        existing = {}
        if raw := self.get_param("env"):
            existing = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
        hosts, primary = self.hosts(dist)
        origins = ",".join(f"https://{h}" for h in hosts)
        env = {
            "DJANGO_DEBUG": "False",
            "DJANGO_SKIP_DOTENV": "1",
            "DJANGO_SECRET_KEY": existing.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50),
            "DJANGO_ADMIN_URL": existing.get("DJANGO_ADMIN_URL") or f"ops-{secrets.token_hex(5)}/",
            "DJANGO_ALLOWED_HOSTS": ",".join(hosts),
            "DJANGO_CSRF_TRUSTED_ORIGINS": origins,
            "CORS_ALLOWED_ORIGINS": origins,
            "CORECART_BASE_URL": primary,
            "CORECART_FRONTEND_URL": primary,
            "DJANGO_BEHIND_PROXY": "True",
            "DJANGO_NUM_PROXIES": "2",  # CloudFront + nginx
            "DJANGO_STATIC_ROOT": "/var/lib/corecart/static",
            "DJANGO_MEDIA_ROOT": "/var/lib/corecart/media",
            "DB_ENGINE": "postgresql", "DB_NAME": "corecart", "DB_USER": "corecart", "DB_HOST": "/run/postgresql",
            "REDIS_URL": "redis://127.0.0.1:6379/0",
            "GUNICORN_BIND": "127.0.0.1:8000", "GUNICORN_WORKERS": "2", "GUNICORN_THREADS": "4",
            "EMAIL_BACKEND": existing.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"),
        }
        # Demo default: no outgoing email (messages go to the app log). Django 6.1's deploy check rejects the
        # console backend, so silence exactly that check, and only while the console backend is in use.
        if env["EMAIL_BACKEND"].endswith("console.EmailBackend"):
            env["DJANGO_SILENCED_SYSTEM_CHECKS"] = "mail.E001"
        else:
            existing.pop("DJANGO_SILENCED_SYSTEM_CHECKS", None)
        # Keep anything added by hand (SMTP settings, etc.) that we don't manage.
        for k, v in existing.items():
            env.setdefault(k, v)
        self.put_param("env", "\n".join(f"{k}={v}" for k, v in env.items()) + "\n")
        return env

    # ------------------------------------------------------------------ release
    def build_bundle(self, skip_build: bool) -> tuple[str, bytes]:
        if not skip_build:
            if not shutil.which("bun"):
                sys.exit("bun is required to build the frontend (or pass --skip-build with frontend/dist present).")
            log("building the React frontend (bun run build)")
            subprocess.run(["bun", "run", "build"], cwd=ROOT / "frontend", check=True)
        if not (ROOT / "frontend/dist/index.html").exists():
            sys.exit("frontend/dist/index.html missing; run the frontend build.")
        files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT,
                               capture_output=True, check=True).stdout.decode().split("\0")
        files = [f for f in files if f and not f.startswith(EXCLUDE_PREFIXES) and (ROOT / f).is_file()]
        files += [str(p.relative_to(ROOT)) for p in (ROOT / "frontend/dist").rglob("*") if p.is_file()]
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True).stdout.strip() or "nogit"
        release_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{sha}"

        def owner_root(ti: tarfile.TarInfo) -> tarfile.TarInfo:
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            ti.mode = 0o755 if ti.mode & 0o111 else 0o644
            return ti
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for f in sorted(set(files)):
                tar.add(ROOT / f, arcname=f, filter=owner_root)
        data = buf.getvalue()
        log(f"release {release_id}: {len(set(files))} files, {len(data) / 1e6:.1f} MB")
        return release_id, data

    def release(self, instance_id: str, skip_build: bool) -> None:
        release_id, data = self.build_bundle(skip_build)
        key = f"releases/{release_id}.tgz"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        rel = f"/opt/corecart/releases/{release_id}"
        self.run(instance_id, f"""set -euo pipefail
export AWS_REGION={self.region} CORECART_PARAM_PREFIX={PARAM}
mkdir -p {rel}
aws s3 cp s3://{self.bucket}/{key} /tmp/{release_id}.tgz --region {self.region} --only-show-errors
tar xzf /tmp/{release_id}.tgz -C {rel} --no-same-owner && rm -f /tmp/{release_id}.tgz
bash {rel}/deploy/aws/remote.sh release {rel}
""", f"install release {release_id}")

    def wait_public(self, dist: dict) -> None:
        dist_id = dist["Id"]
        log("waiting for CloudFront to finish deploying (first time takes ~5-10 min)")
        self.cf.get_waiter("distribution_deployed").wait(Id=dist_id, WaiterConfig={"Delay": 20, "MaxAttempts": 60})
        url = f"https://{dist['DomainName']}"  # custom-domain DNS may not point here yet
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"{url}/api/v1/health/", timeout=15) as r:
                    if r.status == 200:
                        log(f"public health check OK: {url}/api/v1/health/")
                        return
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(10)
        sys.exit(f"{url}/api/v1/health/ did not return 200.")

    def require(self) -> tuple[dict, dict]:
        inst, dist = self.find_instance(), self.find_distribution()
        if not inst or not dist:
            sys.exit("Not deployed yet. Run `deploy.py up` first.")
        if inst["State"]["Name"] != "running":
            sys.exit("The instance is stopped. Run `deploy.py start`.")
        return inst, dist


# ---------------------------------------------------------------------- commands
def cmd_up(d: Deployer, a) -> None:
    log(f"account {d.account}, region {d.region}")
    d.ensure_bucket()
    d.put_param("bucket", d.bucket, secure=False)
    inst = d.ensure_instance(a.instance_type)
    _, origin_dns = d.ensure_eip(inst["InstanceId"])
    origin_secret = d.get_param("origin-secret") or secrets.token_urlsafe(32)
    d.put_param("origin-secret", origin_secret)
    existing = d.get_param("env") or ""
    admin = next((ln.split("=", 1)[1] for ln in existing.splitlines() if ln.startswith("DJANGO_ADMIN_URL=")),
                 None) or f"ops-{secrets.token_hex(5)}/"
    if not existing:  # make sure the admin path baked into CloudFront matches the env we write
        d.put_param("env", f"DJANGO_ADMIN_URL={admin}\n")
    dist = d.ensure_distribution(origin_dns, admin, origin_secret)
    d.update_origin_dns(dist["Id"], origin_dns)
    d.write_env(dist)
    d.wait_ssm(inst["InstanceId"])
    d.release(inst["InstanceId"], a.skip_build)
    d.wait_public(dist)
    cmd_status(d, a)


def cmd_deploy(d: Deployer, a) -> None:
    inst, dist = d.require()
    d.write_env(dist)
    d.release(inst["InstanceId"], a.skip_build)
    d.wait_public(dist)


def cmd_config(d: Deployer, a) -> None:
    inst, dist = d.require()
    d.write_env(dist)
    d.run(inst["InstanceId"], f"AWS_REGION={d.region} bash /opt/corecart/current/deploy/aws/remote.sh config",
          "apply configuration")


def cmd_seed(d: Deployer, a) -> None:
    inst, _ = d.require()
    pw = d.get_param("admin-password")
    if not pw:
        pw = secrets.token_urlsafe(16)
        d.put_param("admin-password", pw)
    out = d.run(inst["InstanceId"], f"""set -euo pipefail
export PATH=/usr/local/bin:$PATH
corecart-manage seed_demo --force  # explicit demo opt-in; random passwords
export DJANGO_SUPERUSER_PASSWORD="$(aws ssm get-parameter --region {d.region} --with-decryption --name {PARAM}/admin-password --query Parameter.Value --output text)"
corecart-manage createsuperuser --noinput --username admin --email admin@example.com 2>/dev/null \\
  && echo "admin user created" || echo "admin user already exists (password unchanged)"
""", "seed demo data + admin user")
    for line in out.splitlines():
        if "password:" in line:
            d.put_param("demo-password", line.rsplit("password:", 1)[1].strip())
    print(f"\nAdmin login: admin / (stored in SSM {PARAM}/admin-password)")
    print(f"Demo logins: demo_vendor, demo_customer / (stored in SSM {PARAM}/demo-password)")


def cmd_status(d: Deployer, a) -> None:
    inst, dist = d.find_instance(), d.find_distribution()
    if not dist:
        print("Not deployed.")
        return
    hosts, url = d.hosts(dist)
    env = d.get_param("env") or ""
    admin = next((ln.split("=", 1)[1] for ln in env.splitlines() if ln.startswith("DJANGO_ADMIN_URL=")), "?")
    print(f"""
  App          {url}/
  API docs     {url}/api/v1/docs/
  Health       {url}/api/v1/health/
  Admin        {url}/{admin}
  CloudFront   {dist['Id']}  ({dist['DomainName']})
  Instance     {inst['InstanceId'] if inst else '-'}  {inst['InstanceType'] if inst else ''}  {inst['State']['Name'] if inst else ''}
  Shell        aws ssm start-session --target {inst['InstanceId'] if inst else '<id>'} --region {d.region}
  Bucket       s3://{d.bucket}
  Secrets      SSM {PARAM}/env, {PARAM}/admin-password, {PARAM}/demo-password
""")


def cmd_domain(d: Deployer, a) -> None:
    inst, dist = d.require()
    names = [n.lower().rstrip(".") for n in a.names]
    arn = None
    for page in d.acm.get_paginator("list_certificates").paginate(
            CertificateStatuses=["PENDING_VALIDATION", "ISSUED"]):
        for c in page["CertificateSummaryList"]:
            if c["DomainName"] == names[0]:
                desc = d.acm.describe_certificate(CertificateArn=c["CertificateArn"])["Certificate"]
                if set(desc.get("SubjectAlternativeNames", [])) == set(names):
                    arn = c["CertificateArn"]
    if not arn:
        log(f"requesting ACM certificate for {', '.join(names)}")
        arn = d.acm.request_certificate(DomainName=names[0], SubjectAlternativeNames=names,
                                        ValidationMethod="DNS", Tags=[TAG])["CertificateArn"]
    for _ in range(20):
        cert = d.acm.describe_certificate(CertificateArn=arn)["Certificate"]
        opts = cert.get("DomainValidationOptions", [])
        if opts and all("ResourceRecord" in o for o in opts):
            break
        time.sleep(3)
    if cert["Status"] != "ISSUED":
        print("\nAdd these DNS records at your DNS provider, then run this command again:\n")
        seen = set()
        for o in opts:
            rr = o["ResourceRecord"]
            if rr["Name"] not in seen:
                seen.add(rr["Name"])
                print(f"  {rr['Type']:6} {rr['Name']}  ->  {rr['Value']}")
        print(f"\n(certificate status: {cert['Status']}; validation usually takes a few minutes after DNS updates)")
        return
    resp = d.cf.get_distribution_config(Id=dist["Id"])
    cfg = resp["DistributionConfig"]
    cfg["Aliases"] = {"Quantity": len(names), "Items": names}
    cfg["ViewerCertificate"] = {"ACMCertificateArn": arn, "SSLSupportMethod": "sni-only",
                                "MinimumProtocolVersion": "TLSv1.2_2021"}
    log("attaching the domain + certificate to CloudFront")
    d.cf.update_distribution(Id=dist["Id"], IfMatch=resp["ETag"], DistributionConfig=cfg)
    dist = d.find_distribution()
    d.write_env(dist)
    d.run(inst["InstanceId"], f"AWS_REGION={d.region} bash /opt/corecart/current/deploy/aws/remote.sh config",
          "apply new hostnames")
    print("\nNow point DNS at CloudFront:")
    for n in names:
        print(f"  CNAME  {n}  ->  {dist['DomainName']}   (apex/root domain: use an ALIAS/ANAME or Route 53 alias)")
    d.wait_public(dist)


def cmd_stop(d: Deployer, a) -> None:
    inst = d.find_instance()
    if inst:
        d.ec2.stop_instances(InstanceIds=[inst["InstanceId"]])
        log("instance stopping (you keep paying only for the disk, IP and S3: ~$5/month)")


def cmd_start(d: Deployer, a) -> None:
    inst = d.find_instance()
    if not inst:
        sys.exit("No instance.")
    d.ec2.start_instances(InstanceIds=[inst["InstanceId"]])
    d.ec2.get_waiter("instance_running").wait(InstanceIds=[inst["InstanceId"]])
    log("instance running; the site is back in ~1 minute")


def cmd_destroy(d: Deployer, a) -> None:
    if not a.yes:
        sys.exit("This deletes the server, database and CloudFront distribution. Re-run with --yes.")
    dist = d.find_distribution()
    if dist:
        resp = d.cf.get_distribution_config(Id=dist["Id"])
        if resp["DistributionConfig"]["Enabled"]:
            log("disabling CloudFront distribution")
            resp["DistributionConfig"]["Enabled"] = False
            d.cf.update_distribution(Id=dist["Id"], IfMatch=resp["ETag"], DistributionConfig=resp["DistributionConfig"])
        d.cf.get_waiter("distribution_deployed").wait(Id=dist["Id"], WaiterConfig={"Delay": 30, "MaxAttempts": 60})
        d.cf.delete_distribution(Id=dist["Id"], IfMatch=d.cf.get_distribution_config(Id=dist["Id"])["ETag"])
        log("CloudFront distribution deleted")
    inst = d.find_instance()
    if inst:
        d.ec2.modify_instance_attribute(InstanceId=inst["InstanceId"], DisableApiTermination={"Value": False})
        d.ec2.terminate_instances(InstanceIds=[inst["InstanceId"]])
        d.ec2.get_waiter("instance_terminated").wait(InstanceIds=[inst["InstanceId"]])
        log("instance terminated")
    for addr in d.ec2.describe_addresses(Filters=[{"Name": "tag:Project", "Values": [NAME]}])["Addresses"]:
        d.ec2.release_address(AllocationId=addr["AllocationId"])
    for sg in d.ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [f"{NAME}-web"]}])["SecurityGroups"]:
        d.ec2.delete_security_group(GroupId=sg["GroupId"])
    role = f"{NAME}-ec2"
    try:
        d.iam.remove_role_from_instance_profile(InstanceProfileName=role, RoleName=role)
        d.iam.delete_instance_profile(InstanceProfileName=role)
        d.iam.detach_role_policy(RoleName=role, PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore")
        d.iam.delete_role_policy(RoleName=role, PolicyName=f"{NAME}-least-privilege")
        d.iam.delete_role(RoleName=role)
    except ClientError:
        pass
    for p in ("env", "origin-secret", "bucket", "admin-password", "demo-password"):
        try:
            d.ssm.delete_parameter(Name=f"{PARAM}/{p}")
        except ClientError:
            pass
    if a.delete_bucket:
        b = d.s.resource("s3").Bucket(d.bucket)
        b.objects.all().delete()
        b.delete()
        log("bucket deleted (including backups)")
    else:
        log(f"kept s3://{d.bucket} (backups). Pass --delete-bucket to remove it.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    p.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    sub = p.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up", help="create/update infrastructure and deploy")
    up.add_argument("--instance-type", default="t4g.micro")
    up.add_argument("--skip-build", action="store_true")
    dep = sub.add_parser("deploy", help="deploy the current code")
    dep.add_argument("--skip-build", action="store_true")
    sub.add_parser("config", help="re-write the Django env in SSM and restart")
    sub.add_parser("seed", help="load demo data and create the admin user")
    sub.add_parser("status")
    dom = sub.add_parser("domain", help="attach a custom domain (ACM certificate + CloudFront alias)")
    dom.add_argument("names", nargs="+")
    sub.add_parser("stop")
    sub.add_parser("start")
    des = sub.add_parser("destroy")
    des.add_argument("--yes", action="store_true")
    des.add_argument("--delete-bucket", action="store_true")
    a = p.parse_args()
    d = Deployer(a.region, a.profile)
    globals()[f"cmd_{a.cmd}"](d, a)


if __name__ == "__main__":
    main()
