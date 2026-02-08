import os


def main() -> int:
    rp_id = os.getenv("PASSKEY_RP_ID", "localhost")
    origin = os.getenv("PASSKEY_RP_ORIGIN", "http://localhost:4321")
    rp_name = os.getenv("PASSKEY_RP_NAME", "Music Board")
    print("Passkey config:")
    print(f"  PASSKEY_RP_ID={rp_id}")
    print(f"  PASSKEY_RP_ORIGIN={origin}")
    print(f"  PASSKEY_RP_NAME={rp_name}")
    print("Passkey endpoints:")
    print("  POST /account/passkeys/options")
    print("  POST /account/passkeys/verify")
    print("  POST /login/passkeys/options")
    print("  POST /login/passkeys/verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
