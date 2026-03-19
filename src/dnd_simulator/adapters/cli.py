from dnd_simulator.service import GameService


def run_cli() -> None:
    """Simple REPL interface for the game."""
    service = GameService()
    session = service.start_game()

    print("=== D&D Simulator ===")
    print(f"Session: {session.session_id}")
    print(f"Year: {session.world.time.year}")
    print("Type 'quit' to exit, 'save' to save game.\n")

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
            data = service.save_game(session.session_id)
            print(f"Game saved. ({len(data)} keys)")
            continue

        response = service.player_action(session.session_id, text)
        print(f"\n{response.text}\n")


if __name__ == "__main__":
    run_cli()
