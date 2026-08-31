from db_test import get_connection

def reset_demo_data():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Order matters: match_players references matches AND players,
        # so it must be cleared before matches can be deleted.
        cursor.execute("DELETE FROM match_players;")
        cursor.execute("DELETE FROM matches;")
        cursor.execute("DELETE FROM queue_entries;")

        # Queues every player currently in the `players` table, regardless
        # of how many there are, with a random latency between 10-100ms.
        cursor.execute("""
            INSERT INTO queue_entries (Player_ID, status, latency_ms)
            SELECT ID, 'waiting', FLOOR(10 + RAND() * 90)
            FROM players;
        """)

        conn.commit()
        print("Demo data reset — all players back in queue.")
    except Exception as err:
        conn.rollback()
        print(f"Reset failed, rolled back: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    reset_demo_data()