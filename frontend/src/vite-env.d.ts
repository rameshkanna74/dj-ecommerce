/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** ISO 4217 code used to format prices (default USD). */
  readonly VITE_CURRENCY?: string
  /** Shop name shown in the header and page titles (default CoreCart). */
  readonly VITE_SHOP_NAME?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
