import os
from pathlib import Path

from dotenv import load_dotenv

from dnd_simulator.llm.client import LlmClient
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

DEFAULT_SAVES_DIR = Path(__file__).resolve().parents[3] / "saves"


def run_cli() -> None:
    """Simple REPL interface for the game."""
    load_dotenv()

    store = JsonFileStore(DEFAULT_SAVES_DIR)

    # Create LLM client if API key is configured
    llm: LlmClient | None = None
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if api_key:
        model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat-v3-0324")
        llm = LlmClient(api_key=api_key, model=model)
        print(f"LLM: {model}")
    else:
        print("LLM: not configured (set OPENROUTER_API_KEY in .env)")

    service = GameService(store=store, llm=llm)
    session = service.start_game()

    print("=== D&D Simulator ===")
    print(f"Session: {session.session_id}")
    print(
        "Commands: look, map, go <direction>, wait [hours], talk <npc>,"
        " nations, nation <id>, settlements, save, saves, load <name>, quit\n"
    )

    # Show starting location
    response = service.player_action(session.session_id, "look")
    print(f"{response.text}\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nFarewell, adventurer.")
            break

        if not text:
            continue

        if text.lower() == "quit":
            print("Farewell, adventurer.")
            break

        if text.lower() == "save":
            name = service.save_game(session.session_id)
            print(f"Game saved as '{name}'.")
            continue

        if text.lower() == "saves":
            saves = service.list_saves()
            if saves:
                for s in saves:
                    print(f"  - {s}")
            else:
                print("  No saves found.")
            continue

        if text.lower().startswith("load "):
            save_name = text[5:].strip()
            try:
                service.load_game(session.session_id, save_name)
                print(f"Loaded '{save_name}'.")
                response = service.player_action(session.session_id, "look")
                print(f"\n{response.text}\n")
            except KeyError:
                print(f"Save '{save_name}' not found.")
            continue

        response = service.player_action(session.session_id, text)
        print(f"\n{response.text}\n")


if __name__ == "__main__":
    run_cli()
