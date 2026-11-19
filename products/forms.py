from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import Category, Product, ProductImage, ProductQuestion, ProductVariant, Review


class ProductFilterForm(forms.Form):
    SORT_CHOICES = [
        ("newest", "Newest"),
        ("price_asc", "Price: low to high"),
        ("price_desc", "Price: high to low"),
        ("popular", "Best selling"),
        ("rating", "Top rated"),
    ]

    q = forms.CharField(required=False, max_length=100, label="Search")
    category = forms.SlugField(required=False)
    min_price = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label="Min price")
    max_price = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label="Max price")
    in_stock = forms.BooleanField(required=False, label="In stock only")
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("min_price"), cleaned.get("max_price")
        if low is not None and high is not None and low > high:
            self.add_error("max_price", "Max price must be greater than min price.")
        return cleaned


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["category", "name", "description", "price", "stock", "cover_image", "is_active"]
        labels = {"is_active": "Visible in marketplace", "cover_image": "Main image"}
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"min": "0"}),
            "cover_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }
        help_texts = {"stock": "When the product has options, stock is tracked per option instead."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.active()

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price is None or price <= Decimal("0"):
            raise forms.ValidationError("Price must be greater than zero.")
        return price


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["attribute_name", "attribute_value", "price_override", "stock", "is_active"]
        labels = {"attribute_name": "Option", "attribute_value": "Value", "price_override": "Price (optional)"}
        widgets = {
            "price_override": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"min": "0"}),
        }


ProductVariantFormSet = inlineformset_factory(
    Product, ProductVariant, form=ProductVariantForm, extra=1, can_delete=True, max_num=20, validate_max=True
)

ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=["image", "alt_text", "position"],
    extra=1,
    can_delete=True,
    max_num=8,
    validate_max=True,
    widgets={"image": forms.ClearableFileInput(attrs={"accept": "image/*"})},
)


class StockUpdateForm(forms.Form):
    stock = forms.IntegerField(min_value=0, max_value=1_000_000)


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(5, 0, -1)], coerce=int
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        labels = {"comment": "Your review"}
        widgets = {"comment": forms.Textarea(attrs={"rows": 4, "maxlength": 2000})}

    def clean_comment(self):
        comment = self.cleaned_data["comment"].strip()
        if len(comment) < 10:
            raise forms.ValidationError("Please write at least 10 characters.")
        if len(comment) > 2000:
            raise forms.ValidationError("Reviews are limited to 2000 characters.")
        return comment


class QuestionForm(forms.ModelForm):
    class Meta:
        model = ProductQuestion
        fields = ["question"]
        labels = {"question": "Ask a question about this product"}
        widgets = {"question": forms.Textarea(attrs={"rows": 3, "maxlength": 1000})}

    def clean_question(self):
        question = self.cleaned_data["question"].strip()
        if len(question) < 5:
            raise forms.ValidationError("Please write a longer question.")
        return question


class AnswerForm(forms.ModelForm):
    class Meta:
        model = ProductQuestion
        fields = ["answer"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 3, "maxlength": 2000})}

    def clean_answer(self):
        answer = self.cleaned_data["answer"].strip()
        if not answer:
            raise forms.ValidationError("Please write an answer.")
        return answer
