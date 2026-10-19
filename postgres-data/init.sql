-- ==========================================
-- 1. SCHEMA DEFINITION
-- ==========================================

-- Table 1: Binders (The "1" side of the 1:N relationship)
CREATE TABLE binders
(
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: Physical Cards (The "N" side of 1:N, and "1" side of 1:1)
CREATE TABLE cards
(
    id               SERIAL PRIMARY KEY,
    binder_id        INT          NOT NULL REFERENCES binders (id) ON DELETE CASCADE,
    name             VARCHAR(100) NOT NULL,
    set_name         VARCHAR(100) NOT NULL,
    collector_number VARCHAR(20)  NOT NULL,
    rarity           VARCHAR(50)  NOT NULL,
    variant          VARCHAR(50) DEFAULT 'Standard',
    acquired_at      DATE        DEFAULT CURRENT_DATE
);

-- Table 3: Grading Certificates (The "1" side of the 1:1 relationship)
-- Notice the UNIQUE constraint on card_id: this enforces a strict 1:1 relationship!
CREATE TABLE grading_certificates
(
    id              SERIAL PRIMARY KEY,
    card_id         INT           NOT NULL UNIQUE REFERENCES cards (id) ON DELETE CASCADE,
    grading_company VARCHAR(20)   NOT NULL,
    cert_number     VARCHAR(50)   NOT NULL UNIQUE,
    grade           NUMERIC(3, 1) NOT NULL CHECK (grade >= 1.0 AND grade <= 10.0),
    graded_at       DATE          NOT NULL
);

-- ==========================================
-- 2. SEED DATA
-- ==========================================

-- Insert Binders
INSERT INTO binders (name, description)
VALUES ('Vintage Vault', 'High-value WOTC era holos and graded slabs'),
       ('Modern Alt Arts', 'Scarlet & Violet and Sword & Shield full arts'),
       ('Trade Binder', 'Duplicates and playable cards for locals');

-- Insert Cards (1:N relationship to Binders)
INSERT INTO cards (binder_id, name, set_name, collector_number, rarity, variant, acquired_at)
VALUES
-- Cards in 'Vintage Vault' (binder_id = 1)
(1, 'Charizard', 'Base Set', '4/102', 'Holo Rare', '1st Edition Shadowless', '2022-05-14'),
(1, 'Lugia', 'Neo Genesis', '9/111', 'Holo Rare', '1st Edition', '2023-01-20'),
(1, 'Blastoise', 'Base Set', '2/102', 'Holo Rare', 'Unlimited', '2021-11-03'),

-- Cards in 'Modern Alt Arts' (binder_id = 2)
(2, 'Umbreon VMAX', 'Evolving Skies', '215/203', 'Secret Rare', 'Alt Art', '2023-08-19'),
(2, 'Giratina V', 'Lost Origin', '186/196', 'Ultra Rare', 'Alt Art', '2024-02-10'),
(2, 'Gardevoir ex', 'Paldean Fates', '233/091', 'Special Illustration Rare', 'Shiny Holo', '2024-04-05'),

-- Cards in 'Trade Binder' (binder_id = 3)
(3, 'Iono', 'Paldea Evolved', '269/193', 'Special Illustration Rare', 'Full Art', '2024-06-12'),
(3, 'Pidgeot ex', 'Obsidian Flames', '225/197', 'Special Illustration Rare', 'Full Art', '2024-07-01');

-- Insert Grading Certificates (1:1 relationship to Cards)
-- Only some cards are graded (slabs), others remain "raw" in the binder
INSERT INTO grading_certificates (card_id, grading_company, cert_number, grade, graded_at)
VALUES (1, 'PSA', 'PSA-84920194', 9.0, '2022-08-01'),
       (2, 'BGS', 'BGS-00149281', 9.5, '2023-03-15'),
       (4, 'PSA', 'PSA-91827364', 10.0, '2023-10-10'),
       (6, 'CGC', 'CGC-40918273', 9.5, '2024-05-22');