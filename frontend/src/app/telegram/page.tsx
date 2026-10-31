import { Metadata } from "next";
import { TelegramConsole } from "../../telegram/TelegramConsole";

export const metadata: Metadata = {
  title: "Telegram · NIO",
};

export default function TelegramPage() {
  return <TelegramConsole />;
}
