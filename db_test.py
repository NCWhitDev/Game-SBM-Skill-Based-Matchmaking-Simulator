# schema → seeded data → SQL join → Python fetch → pure matching function with correct edge-case handling.
import os
import time
from dotenv import load_dotenv
import mysql.connector
from rich.console import Console
from rich.panel import Panel
# ========================================================================================================
console = Console()
load_dotenv() # Loads environment variables from a .env file into the program's environment.

"""
Establishes a connection to the MySQL database using credentials from environment variables.
"""
def get_connection(): # Establishes a connection to the MySQL database using credentials from environment variables.
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password=os.getenv("DB_PASSWORD"),
        database="Matchmaking"
    )

"""
Fetches all players currently in the queue with a status of 'waiting'.
"""
def fetch_waiting_players(conn): # Fetches all players currently in the queue with a status of 'waiting'.
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT q.ID AS queue_id, p.ID AS player_id, p.Player_Name, p.skill_rating, q.latency_ms,
            TIMESTAMPDIFF(SECOND, q.queued_at, NOW()) AS wait_seconds
        FROM queue_entries q
        JOIN players p ON q.Player_ID = p.ID
        WHERE q.status = 'waiting';
    """)
    rows = cursor.fetchall() # Fetch all rows from the executed query
    cursor.close()
    return rows

"""
Finds matching pairs of players based on skill rating and latency.
- candidates.copy() — this makes a shallow copy of the list itself (a new list object, same dict references inside it).
- sorted(candidates.copy(), key=lambda c: c['skill_rating']) — sorted() returns a new sorted list rather than sorting in place. 
- The key argument specifies a function of one argument that is used to extract a comparison key from each list element. In this case, it sorts the candidates based on their 'skill_rating' value.
"""
def find_matches(candidates, max_skill_diff=600, max_latency_diff=50):
    candidates = sorted(candidates.copy(), key=lambda c: c['skill_rating'])
    matches = []
    match_not_found = []
    while candidates:
        player = candidates.pop(0)
        matched = False
        for other in candidates:
            player_threshold = effective_skill_diff(max_skill_diff, player['wait_seconds'])
            other_threshold = effective_skill_diff(max_skill_diff, other['wait_seconds'])
            combined_threshold = max(player_threshold, other_threshold)

            if (abs(player['skill_rating'] - other['skill_rating']) <= combined_threshold) and \
               (abs(player['latency_ms'] - other['latency_ms']) <= max_latency_diff):
                matches.append((player, other))
                candidates.remove(other)
                matched = True
                break
        if not matched:
            match_not_found.append(player)
            continue
    return matches, match_not_found

"""
Updates the database to mark two players as matched.
"""
def claim_match(conn, player1_id, player2_id):  # Updates the database to mark two players as matched.
    cursor = conn.cursor()
    try:
        cursor.execute("""
                INSERT INTO matches (match_status, match_start_time)
                VALUES (%s, NOW())""", ('in_progress',))
        match_id = cursor.lastrowid  # Get the ID of the newly created match

        cursor.execute("""
                       INSERT INTO match_players (Match_ID, Player_ID, team_side)
                          VALUES (%s, %s, %s), (%s, %s, %s)""",
                       (match_id, player1_id, 0, match_id, player2_id, 1))

        cursor.execute("""
                          UPDATE queue_entries
                              SET status = 'matched'
                              WHERE Player_ID IN (%s, %s)""", (player1_id, player2_id))
        conn.commit()  # Commit the transaction to save changes to the database
        return match_id
    except mysql.connector.Error as err:
        conn.rollback()  # Rollback the transaction in case of an error
        print(f"Match claim failed, rolled back: {err}")
        return None
    finally:
        cursor.close()  # Ensure the cursor is closed after the operation


"""
Calculates the effective skill difference allowed based on how long a player has been waiting.
"""
def effective_skill_diff(base_diff, wait_seconds, max_diff=1500):  # Calculates the effective skill difference allowed based on how long a player has been waiting.
    time_modifier = wait_seconds // 60
    widened = base_diff + time_modifier * 50
    return min(widened, max_diff)  # Increases the effective skill difference allowed based on how long a player has been waiting.


"""
Updates the database to mark matches as finished if they have been in progress for longer than a specified duration.
"""
def finished_match(conn, match_duration_seconds=20):  # Updates the database to mark a match as finished.
    cursor = conn.cursor(dictionary=True) # Create a cursor that returns rows as dictionaries for easier access to column values by name
    cursor.execute("""
        SELECT ID FROM matches
        WHERE match_status = 'in_progress'
        AND TIMESTAMPDIFF(SECOND, match_start_time, NOW()) >= %s
    """, (match_duration_seconds,))
    finished = cursor.fetchall() # Fetch all matches that have been in progress for longer than the specified duration
    cursor.close()

    for match in finished:
        match_id = match['ID']
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT Player_ID FROM match_players WHERE Match_ID = %s
            """, (match_id,))
            players_in_match = cursor.fetchall() # Fetch all players in the finished match

            cursor.execute("""
                UPDATE matches SET match_status = 'completed', match_end_time = NOW()
                WHERE ID = %s
            """, (match_id,))

            for row in players_in_match: # Loop through each player in the finished match
                cursor.execute("""
                    INSERT INTO queue_entries (Player_ID, status, latency_ms)
                    VALUES (%s, 'waiting', FLOOR(10 + RAND() * 90))
                """, (row['Player_ID'],))

            conn.commit() # Commit the transaction to save changes to the database
            console.print(f"[yellow]Match #{match_id} ended — both players back in queue.[/yellow]")
        except mysql.connector.Error as err:
            conn.rollback() # Rollback the transaction in case of an error
            print(f"Failed to close out match {match_id}, rolled back: {err}")
        finally:
            cursor.close()


# ===== Rich display functions =====

"""
Displays a match between two players in a formatted panel using the Rich library.
"""
def display_match(p1, p2, match_id):
    text = (
        f"[bold cyan]{p1['Player_Name']}[/bold cyan] "
        f"(Skill: {p1['skill_rating']}, {p1['latency_ms']}ms)\n"
        f"[bold]vs[/bold]\n"
        f"[bold magenta]{p2['Player_Name']}[/bold magenta] "
        f"(Skill: {p2['skill_rating']}, {p2['latency_ms']}ms)"
    )
    console.print(Panel(text, title=f"Match #{match_id} Found!", border_style="green"))


"""
Displays a player who is still waiting in the queue.
"""
def display_waiting(p):
    console.print(f"[dim]{p['Player_Name']} ({p['skill_rating']}, {p['latency_ms']}ms) still waiting...[/dim]")

# ===== Main execution block =====
if __name__ == "__main__":
    conn = get_connection()
    print("Matchmaking worker started. Press Ctrl+C to stop.")
    
    try:
        while True:
            finished_match(conn) # players who have been in a match for 20 seconds are returned to the queue
            candidates = fetch_waiting_players(conn)
            pairs, unmatched = find_matches(candidates)

            for p1, p2 in pairs:
                match_id = claim_match(conn, p1['player_id'], p2['player_id'])
                if match_id:
                    display_match(p1, p2, match_id)
                else:
                    print(f"Failed to claim match for {p1['Player_Name']} and {p2['Player_Name']}.")

            for p in unmatched:
                    display_waiting(p)
            print(f"Total matches found: {len(pairs)}")

            print(f"Tick complete. {len(pairs)} matches made, {len(unmatched)} still waiting.")
            time.sleep(5)

    except KeyboardInterrupt:
        print("\nShutting down worker...")
    finally:
        conn.close()
        print("Connection closed.")