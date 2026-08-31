CREATE SCHEMA IF NOT EXISTS Matchmaking;

CREATE TABLE Matchmaking.players (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Player_Name VARCHAR(100) NOT NULL,
    skill_rating INT NOT NULL,
    region VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Matchmaking.queue_entries (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    Player_ID INT NOT NULL,
    status ENUM('waiting', 'matched', 'canceled') NOT NULL,
    queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    latency_ms INT NOT NULL,
    FOREIGN KEY (Player_ID) REFERENCES Matchmaking.players(ID)
);

CREATE TABLE Matchmaking.matches (
    ID INT AUTO_INCREMENT PRIMARY KEY,
    match_status ENUM('pending', 'in_progress', 'completed') NOT NULL,
    match_start_time TIMESTAMP NULL,
    match_end_time TIMESTAMP NULL
);

CREATE TABLE Matchmaking.match_players (
    Match_ID INT NOT NULL,
    Player_ID INT NOT NULL,
    team_side TINYINT NOT NULL CHECK (team_side IN (0, 1)),
    PRIMARY KEY (Match_ID, Player_ID),
    FOREIGN KEY (Match_ID) REFERENCES Matchmaking.matches(ID),
    FOREIGN KEY (Player_ID) REFERENCES Matchmaking.players(ID)
);

CREATE INDEX idx_queue_status ON Matchmaking.queue_entries(status);