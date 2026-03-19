from pathlib import Path

from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

DEFAULT_SAVES_DIR = Path(__file__).resolve().parents[3] / "saves"


def run_cli() -> None:
    """Simple REPL interface for the game."""
    store = JsonFileStore(DEFAULT_SAVES_DIR)
    service = GameService(store=store)
    session = service.start_game()

    print("=== D&D Simulator ===")
    print(f"Session: {session.session_id}")
    print(f"Year: {session.world.time.year}")
    print("Type 'quit' to exit, 'save' to save, 'saves' to list saves.\n")

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

        response = service.player_action(session.session_id, text)
        print(f"\n{response.text}\n")


if __name__ == "__main__":
    run_cli()
