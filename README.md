# Session Matchmaking Simulator

A simulated matchmaking backend that models how a live multiplayer game
queues, pairs, and matches players built with a MySQL schema and a
Python worker that ticks continuously, pulling waiting players and
pairing them by skill rating and latency.

## 1. Introduction & Purpose

Matchmaking is one of those systems that looks simple from the outside
("just pair similar-skill players together") but touches a surprising
number of real backend engineering concerns once you build it: relational
schema design, race conditions around claiming a shared resource (a
player who's about to be matched), fairness over time (a player who's
been waiting a while should have an easier time finding a match), and
data integrity under an always-running process.

This project simulates that system end to end:

- A MySQL schema models players, queue tickets, matches, and match
  rosters.
- A Python worker runs an infinite loop ("tick"), each cycle pulling
  everyone currently `waiting`, pairing compatible players, and
  persisting the result back to the database.
- Matching considers **skill rating**, **latency**, and **wait time**
  (a player who's waited longer gets a wider acceptable skill range,
  so nobody gets stuck in queue forever).
- Matches are **claimed transactionally** a match is only ever
  fully created or not created at all, never left half-written if
  something fails partway through.

The goal wasn't just "make it work," but to intentionally touch
concurrency-adjacent problems (atomic claims, race conditions,
data-integrity constraints) even though the worker itself is
single-threaded, the same reasoning that shows up in real
multiplayer backend systems, without needing a networked game server
to demonstrate it.

## 2. Tools Used & Why

| Tool | Purpose | Why this choice |

**MySQL** Stores players, queue tickets, matches, and match rosters | Relational structure fits this domain well , players, queue entries, and matches all reference each other, and foreign keys + constraints let the *database itself* enforce rules (like "a player can't be queued twice at once") rather than relying on application code to remember to check.

**MySQL Workbench** Writing/running schema and seed SQL, inspecting tables visually | Easier to review multi-statement scripts and catch syntax errors before running, versus typing line-by-line in a shell.

**MySQL Shell** Quick ad-hoc queries and connection troubleshooting | Useful for fast checks (`SELECT * FROM ...`) without opening the full Workbench GUI. |

**Python** The matchmaking worker itself | Pairing logic, wait-time math, and the tick loop are easier to write, test, and reason about in Python than in raw SQL. |

| **`mysql-connector-python`** | Python ↔ MySQL communication | Official Oracle-maintained MySQL driver; supports parameterized queries (`%s` placeholders) which protect against SQL injection, and transactions (`commit`/`rollback`), which the atomic claim step depends on. |
| **`python-dotenv`** | Loads DB credentials from a `.env` file | Keeps the database password out of source code — `.env` is git-ignored, so credentials never get committed or shared accidentally. |
| **`rich`** | Colored/boxed terminal output for live match announcements | Makes the worker's output demo-able and legible at a glance, instead of scrolling plain text. |

## 3. How to Use & Test It

### One-time setup

1. Make sure the local MySQL service is running (Windows: search
   **Services**, confirm `MySQL80` shows **Running**).
2. Create a `.env` file in the project root containing:
   ```
   DB_PASSWORD=your_mysql_root_password
   ```
   (Never commit this file it should be listed in `.gitignore`.)
3. Install Python dependencies:
   ```
   pip install mysql-connector-python python-dotenv rich
   ```
4. Run the schema script (in MySQL Workbench or MySQL Shell) to create
   the `Matchmaking` schema and its four tables: `players`,
   `queue_entries`, `matches`, and `match_players`.

### Running the worker

```
python db_test.py
```

This starts the matchmaking loop: every 5 seconds it fetches everyone
`waiting`, attempts to pair them by skill + latency (with wait-time
widening for players who've been queued a while), and claims any
successful pairs transactionally. Live matches print as colored
panels; unmatched players print as dimmed status lines.

Press **Ctrl+C** to stop the worker shuts down gracefully and closes
its database connection rather than crashing mid-transaction.

### Resetting for a demo

Once everyone in the queue has been matched, there's nothing left for
the worker to do on future runs. To reset the queue back to a clean
state (all 10 seeded players `waiting` again, all matches cleared):

```
python reset_demo.py
```

This wipes `match_players`, `matches`, and `queue_entries` (in that
order, to respect foreign key constraints) and re-queues all existing
players it does **not** touch or duplicate the `players` table
itself.

### Things worth testing / observing

- **Skill + latency filtering**: seed two players with a small skill
  gap but a large latency gap they should *not* match, proving the
  latency filter is a real hard constraint, not just a tiebreaker.
- **Wait-time widening**: a player who's waited long enough should
  eventually match a much higher/lower-skill opponent than the base
  threshold would normally allow.
- **Duplicate-queue protection**: try inserting a second `waiting`
  row for a player who already has one MySQL should reject it via
  the `idx_unique_waiting_player` constraint.
- **Transactional safety**: if a claim fails partway (e.g., a
  duplicate `match_players` entry), the whole match should roll back
  no partial match should ever persist in the database.

### Known limitation

The pairing algorithm is **greedy**, not globally optimal: it sorts
by skill and pairs the first compatible candidate it finds, rather
than searching for the *best possible* set of pairings. In practice
this means two players with a very close skill match can sometimes
end up separated because one of them got claimed by a "good enough"
match first. This was an intentional simplification for the scope of
this project, and a legitimate real-world tradeoff a smarter (but
slower) matching strategy would need to compare all possible pairings
before committing to any of them.
