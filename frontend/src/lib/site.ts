export const SHOP_NAME = import.meta.env.VITE_SHOP_NAME ?? "CoreCart"

/** Set the document title for a page ("Product · CoreCart"). */
export function pageTitle(title?: string) {
  return title ? `${title} · ${SHOP_NAME}` : `${SHOP_NAME} — independent makers, one cart`
}
