export const gameIconUrls = {
  book: new URL("../assets/icons/game-icon-pack/book.svg", import.meta.url).href,
  chat: new URL("../assets/icons/game-icon-pack/chat.svg", import.meta.url).href,
  download: new URL("../assets/icons/game-icon-pack/download.svg", import.meta.url).href,
  file: new URL("../assets/icons/game-icon-pack/file.svg", import.meta.url).href,
  folder: new URL("../assets/icons/game-icon-pack/folder.svg", import.meta.url).href,
  link: new URL("../assets/icons/game-icon-pack/link.svg", import.meta.url).href,
  nodes: new URL("../assets/icons/game-icon-pack/nodes.svg", import.meta.url).href,
  pause: new URL("../assets/icons/game-icon-pack/pause.svg", import.meta.url).href,
  play: new URL("../assets/icons/game-icon-pack/play.svg", import.meta.url).href,
  refresh: new URL("../assets/icons/game-icon-pack/refresh.svg", import.meta.url).href,
  review: new URL("../assets/icons/game-icon-pack/review.svg", import.meta.url).href,
  save: new URL("../assets/icons/game-icon-pack/save.svg", import.meta.url).href,
  search: new URL("../assets/icons/game-icon-pack/search.svg", import.meta.url).href,
  settings: new URL("../assets/icons/game-icon-pack/settings.svg", import.meta.url).href,
  upload: new URL("../assets/icons/game-icon-pack/upload.svg", import.meta.url).href,
} as const;

export type GameIconName = keyof typeof gameIconUrls;

