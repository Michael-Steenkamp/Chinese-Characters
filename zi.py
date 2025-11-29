import json
import os
import random
import sys
import time
from typing import Any, Dict, List

# ==========================================
# -------- Penalties and Rewards -----------
# ==========================================
# Weights determine how likely a card is to appear.
# Higher weight = appears more often (needs practice).
PENALTY_SKIP = 2.0
PENALTY_INCORRECT = 4.0
REWARD_STREAK = 0.25
REWARD_CORRECT = 1.0
MAX_WEIGHT = 20.0
MIN_WEIGHT = 0.1

# ==========================================
# ------------ File Paths ------------------
# ==========================================
JSON_DIR = "json"
PROGRESS_DIR = "progress"
DATA_FILE_PATH = os.path.join(JSON_DIR, "zi.json")
PROGRESS_FILE_PATH = os.path.join(PROGRESS_DIR, "zi-progress.json")

# ==========================================
# ----------------- Icons ------------------
# ==========================================
icon_proficiency = "🧠"
icon_time = "  "
icon_streak = "  "
icon_accuracy = "  "
icon_seen = "  "
icon_mastery = "⭐"
icon_correct = "✔ "
icon_incorrect = "✖ "


# ==========================================
# ----------------- UI ---------------------
# ==========================================
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")


# ==========================================
# ----------- Data Handling ----------------
# ==========================================
def load_json(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return []


def save_json(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_progress(data_entries: List[Dict], progress_entries: List[Dict]) -> List[Dict]:
    """
    Ensures every character in zi.json has a corresponding entry in progress.json.
    Backfills missing keys (like total_time) for existing entries.
    """
    # Create a map of existing progress for fast lookup
    progress_map = {p["character"]: p for p in progress_entries}

    synced_list = []

    for item in data_entries:
        char = item["character"]
        if char in progress_map:
            entry = progress_map[char]
            # Backfill new tracking fields if they don't exist in old progress files
            if "total_time" not in entry:
                entry["total_time"] = 0.0
            synced_list.append(entry)
        else:
            # Create new progress entry
            synced_list.append(
                {
                    "character": char,
                    "weight": 10.0,
                    "streak": 0,
                    "attempts": 0,
                    "correct": 0,
                    "total_time": 0.0,
                }
            )

    return synced_list


# ==========================================
# ---------- Statistics Logic --------------
# ==========================================
def get_session_metadata(progress: List[Dict]) -> tuple[float, float]:
    """
    Calculates the total (overall) proficiency and total time spent.
    Proficiency is 0-100% based on how close weights are to MIN_WEIGHT.
    """
    if not progress:
        return 0.0, 0.0

    total_weight = sum(p["weight"] for p in progress)
    total_time = sum(p.get("total_time", 0.0) for p in progress)

    avg_weight = total_weight / len(progress)
    weight_range = MAX_WEIGHT - MIN_WEIGHT

    # Normalized difficulty: 0.0 = easy (MIN_WEIGHT), 1.0 = hard (MAX_WEIGHT)
    normalized_avg_difficulty = (avg_weight - MIN_WEIGHT) / weight_range

    # Proficiency: 100.0 = easy, 0.0 = hard
    proficiency_percent = (1.0 - normalized_avg_difficulty) * 100.0

    # Clamp values just in case
    proficiency_percent = max(0.0, min(100.0, proficiency_percent))

    return proficiency_percent, total_time


def display_session_summary(
    progress, session_correct, session_attempts, time_change_minutes, start_proficiency
):
    """
    Displays the final dashboard summary.
    """
    # --- Calculate Session Stats ---
    session_accuracy = (
        (session_correct / session_attempts * 100) if session_attempts > 0 else 0
    )

    # --- Calculate Global Stats ---
    end_proficiency, end_total_time = get_session_metadata(progress)
    proficiency_change = end_proficiency - start_proficiency

    total_words = len(progress)
    words_seen = sum(1 for p in progress if p["attempts"] > 0)

    overall_total_correct = sum(p["correct"] for p in progress)
    overall_total_attempts = sum(p["attempts"] for p in progress)
    overall_accuracy = (
        (overall_total_correct / overall_total_attempts * 100)
        if overall_total_attempts > 0
        else 0
    )

    # "Mastered" = weight is within bottom 5% of the range
    mastery_threshold = MIN_WEIGHT + (MAX_WEIGHT - MIN_WEIGHT) * 0.05
    words_mastered = sum(1 for p in progress if p["weight"] <= mastery_threshold)

    clear_terminal()
    print()
    print(f"{bcolors.HEADER}╔══ Session Summary ════════════════════════{bcolors.ENDC}")
    print(f"║ {icon_time}Time:        +{time_change_minutes:.2f} minutes")
    print(
        f"║ {icon_accuracy}Accuracy:     {session_accuracy:.1f}% ({session_correct} / {session_attempts})"
    )
    print(
        f"║ {icon_proficiency} Change:      {'+' if proficiency_change > 0 else ''}{proficiency_change:.2f}%"
    )
    print(f"{bcolors.HEADER}╚═══════════════════════════════════════════{bcolors.ENDC}")
    print()
    print(f"{bcolors.OKCYAN}╔══ Overall Progress ═══════════════════════{bcolors.ENDC}")
    print(f"║ {icon_proficiency} Proficiency:  {end_proficiency:.1f}%")
    print(
        f"║ {icon_accuracy}Accuracy:     {overall_accuracy:.1f}% ({overall_total_correct}/{overall_total_attempts})"
    )
    print(f"║ {icon_seen}Seen:         {words_seen} / {total_words} words")
    print(f"║ {icon_mastery} Mastered:     {words_mastered} / {total_words} words")
    print(f"║ {icon_time}Total Time:   {end_total_time / 3600:.2f} hours")
    print(f"{bcolors.OKCYAN}╚═══════════════════════════════════════════{bcolors.ENDC}")
    print()


# ==========================================
# ------------- Core Logic -----------------
# ==========================================
def get_weighted_random_item(data, progress):
    """Selects an index based on the weights in the progress list."""
    weights = [p["weight"] for p in progress]
    indices = range(len(data))
    selected_index = random.choices(indices, weights=weights, k=1)[0]
    return selected_index


def run_quiz():
    data = load_json(DATA_FILE_PATH)
    raw_progress = load_json(PROGRESS_FILE_PATH)

    if not data:
        print(f"{bcolors.FAIL}No data found in {DATA_FILE_PATH}{bcolors.ENDC}")
        return

    # Sync progress with current data
    progress = sync_progress(data, raw_progress)

    # Stats Initialization
    session_correct = 0
    session_attempts = 0
    start_proficiency, start_total_time = get_session_metadata(progress)

    clear_terminal()
    print(f"{bcolors.HEADER}--- Zi Quiz (One-Trick Pony) ---{bcolors.ENDC}")
    print(
        f"{bcolors.OKCYAN}Type the pinyin (with numbers, e.g., 'ni3'). Type 'exit' to quit.{bcolors.ENDC}\n"
    )

    try:
        while True:
            # 1. Get Candidate
            idx = get_weighted_random_item(data, progress)
            item = data[idx]
            prog = progress[idx]

            target_char = item["character"]
            target_pinyin = item["pinyin"]

            # 2. Display Prompt
            print(
                f"{bcolors.HEADER}-------------------------------------------{bcolors.ENDC}"
            )
            print(
                f"Character:  {bcolors.BOLD}{bcolors.OKBLUE}{target_char}{bcolors.ENDC}"
            )

            # 3. Get Input (Time it)
            start_time = time.time()
            user_input = input(f"Pinyin?     ").strip().lower()
            end_time = time.time()

            elapsed_time = end_time - start_time

            if user_input in ["exit", "quit", "q"]:
                break

            # Update generic stats
            prog["attempts"] += 1
            prog["total_time"] += elapsed_time
            session_attempts += 1

            # 4. Check Answer & Update Weights
            is_correct = user_input == target_pinyin.lower()

            if is_correct:
                print(
                    f"            {bcolors.OKGREEN}{bcolors.BOLD}CORRECT!{bcolors.ENDC} ({elapsed_time:.2f}s)"
                )
                prog["streak"] += 1
                prog["correct"] += 1
                session_correct += 1

                # Decrease weight
                reduction = REWARD_CORRECT + (REWARD_STREAK * prog["streak"])
                prog["weight"] = max(MIN_WEIGHT, prog["weight"] - reduction)
            else:
                print(
                    f"            {bcolors.FAIL}{bcolors.BOLD}WRONG.{bcolors.ENDC} Answer: {target_pinyin}"
                )
                prog["streak"] = 0
                # Increase weight
                prog["weight"] = min(MAX_WEIGHT, prog["weight"] + PENALTY_INCORRECT)

            # 5. Show Metadata (Definition & Words)
            print(f"\n{bcolors.OKCYAN}Definition:{bcolors.ENDC} {item['definition']}")

            if "examples" in item and item["examples"]:
                print(f"{bcolors.WARNING}Words:{bcolors.ENDC}")
                for ex in item["examples"]:
                    w = ex.get("word", "")
                    p = ex.get("pinyin", "")
                    d = ex.get("definition", "")
                    print(f"  • {w} ({p}): {d}")

            # Show debug stats
            print(
                f"\n{bcolors.OKBLUE}[Stats: Streak {prog['streak']} | Weight {prog['weight']:.2f}]{bcolors.ENDC}"
            )

            # 6. Save Progress (Save frequently to avoid data loss)
            save_json(progress, PROGRESS_FILE_PATH)

            # Pause before next card
            input(f"\n{bcolors.OKCYAN}Press Enter...{bcolors.ENDC}")
            clear_terminal()

    except KeyboardInterrupt:
        print("\nSession Interrupted.")
    finally:
        # Final Save
        save_json(progress, PROGRESS_FILE_PATH)

        # Calculate final stats for summary
        end_proficiency, end_total_time = get_session_metadata(progress)
        time_change_minutes = (end_total_time - start_total_time) / 60.0

        display_session_summary(
            progress,
            session_correct,
            session_attempts,
            time_change_minutes,
            start_proficiency,
        )
        input("Press Enter to exit...")


if __name__ == "__main__":
    run_quiz()
