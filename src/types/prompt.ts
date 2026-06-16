export type PromptRequest = {
  prompt: string
  // An attached document. When present, the adapter posts multipart to
  // /chat/upload; the file is extracted to text server-side, so the text
  // never round-trips back to the browser.
  file?: File
  context?: {
    conversationId?: string
  }
}
