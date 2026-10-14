import os
import math
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load Gemini API key from .env
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = "gemini-flash-latest"

client = genai.Client(api_key=API_KEY) if API_KEY else None

TIMETABLE_SYSTEM = (
    "You analyze college timetables. Summarize daily workload, free periods "
    "and study-planning suggestions. Never invent class timings."
)
CHATBOT_SYSTEM = (
    "You are a helpful college AI assistant. Help with engineering subjects, "
    "exams, study planning, college life, attendance and marks. "
    "Do not invent official rules."
)


def line():
    print("-" * 50)


# ---------------------------------------------------------------- input ----
def get_number(prompt, minimum=None, maximum=None,
               default=None, min_exclusive=False):
    """Ask for a number. Empty input returns `default` if one is given."""
    while True:
        raw = input(prompt).strip()

        if raw == "" and default is not None:
            return default

        try:
            value = float(raw)
        except ValueError:
            print("Enter a valid number.")
            continue

        if not math.isfinite(value):
            print("Enter a valid number.")
            continue

        if minimum is not None:
            if min_exclusive and value <= minimum:
                print(f"Value must be greater than {minimum:g}.")
                continue
            if not min_exclusive and value < minimum:
                print(f"Value must be at least {minimum:g}.")
                continue

        if maximum is not None and value > maximum:
            print(f"Value must not exceed {maximum:g}.")
            continue

        return value


def get_int(prompt, minimum=None, maximum=None):
    """Ask for a whole number (rejects 2.5 instead of truncating it)."""
    while True:
        value = get_number(prompt, minimum, maximum)
        if value != int(value):
            print("Enter a whole number.")
            continue
        return int(value)


def yes_no(prompt):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no", ""):
            return False
        print("Please answer y or n.")


# ------------------------------------------------------------ 1. Attendance
def attendance_calculator():
    line()
    print("ATTENDANCE CALCULATOR")
    line()

    attended = get_number("Classes attended: ", 0)
    total = get_number("Total classes held: ", 0)

    if attended > total:
        print("Attended classes cannot exceed total classes.")
        return

    if total == 0:
        print("No classes have been held yet.")
        return

    target = get_number("Target attendance % (default 75): ",
                        0, 100, default=75.0, min_exclusive=True)

    percentage = attended / total * 100
    print(f"\nCurrent attendance: {percentage:.2f}%")

    if percentage >= target:
        if target == 100:
            print("To stay at 100%, attend every future class.")
        else:
            max_misses = math.floor(attended / (target / 100) - total + 1e-9)
            print(f"Maximum additional classes you can miss: "
                  f"{max(0, max_misses)}")
    else:
        if target == 100:
            print("You can no longer reach exactly 100% — "
                  "every missed class is permanent.")
        else:
            needed = math.ceil(
                (target * total - 100 * attended) / (100 - target) - 1e-9
            )
            print(f"Consecutive classes to attend: {max(0, needed)}")
            print("Assuming you attend every future class.")


# ---------------------------------------------------------------- 2. Marks
def marks_calculator():
    line()
    print("MARKS CALCULATOR")
    line()

    count = get_int("Number of subjects: ", 1, 100)
    subjects = []

    for i in range(count):
        print(f"\nSubject {i + 1}")
        name = input("Subject name: ").strip() or f"Subject {i + 1}"
        maximum = get_number("Maximum marks: ", 0, min_exclusive=True)
        obtained = get_number("Marks obtained: ", 0, maximum)
        subjects.append((name, obtained, maximum))

    total_obtained = sum(s[1] for s in subjects)
    total_maximum = sum(s[2] for s in subjects)
    percentage = total_obtained / total_maximum * 100

    print("\nSUBJECT RESULTS")
    line()

    for name, obtained, maximum in subjects:
        print(f"{name}: {obtained:g}/{maximum:g} "
              f"({obtained / maximum * 100:.2f}%)")

    line()
    print(f"Total marks: {total_obtained:g}/{total_maximum:g}")
    print(f"Overall percentage: {percentage:.2f}%")

    target = get_number("\nTarget percentage (0 to skip): ", 0, 100)

    if target > 0:
        remaining = get_number(
            "Marks still available in upcoming exams (0 if none): ", 0
        )
        # Target is measured over everything: done + upcoming.
        grand_total = total_maximum + remaining
        needed = target / 100 * grand_total - total_obtained

        if needed <= 0:
            print("You have already achieved your target.")
        elif needed <= remaining:
            print(f"You need {needed:.2f} out of the {remaining:g} "
                  f"upcoming marks ({needed / remaining * 100:.1f}%).")
        else:
            print("Target is not possible with the marks still available.")

    print("CGPA depends on your college's grading rules.")


# ------------------------------------------------------------ 3. Timetable
def to_minutes(value):
    h, m = map(int, value.split(":"))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time.")
    return h * 60 + m


def parse_entry(row):
    """Return (day, start_min, end_min, start, end, subject) or raise."""
    parts = [p.strip() for p in row.split("|")]
    if len(parts) != 3:
        raise ValueError("Use Day | HH:MM-HH:MM | Subject")

    day, time_range, subject = parts
    times = time_range.split("-")
    if len(times) != 2 or not day or not subject:
        raise ValueError("Invalid timetable entry.")

    start, end = times[0].strip(), times[1].strip()
    try:
        start_min, end_min = to_minutes(start), to_minutes(end)
    except ValueError:
        raise ValueError("Times must look like 09:00-10:00.")

    if end_min <= start_min:
        raise ValueError("End time must be after start time.")

    return day, start_min, end_min, start, end, subject


def timetable_analyzer():
    line()
    print("TIMETABLE ANALYZER")
    line()
    print("Enter: Monday | 09:00-10:00 | Mathematics")
    print("Press Enter on an empty line to finish.\n")

    entries = {}

    while True:
        row = input().strip()
        if not row:
            break

        try:
            day, start_min, end_min, start, end, subject = parse_entry(row)
        except ValueError as error:
            print(f"Invalid entry: {error}")
            continue

        group = entries.setdefault(day.lower(), {"day": day, "classes": []})

        # Reject only the offending line; keep everything else.
        clash = next((c for c in group["classes"]
                      if start_min < c[1] and c[0] < end_min), None)
        if clash:
            print(f"Rejected: overlaps with {clash[4]} "
                  f"({clash[2]}-{clash[3]}) on {group['day']}.")
            continue

        group["classes"].append((start_min, end_min, start, end, subject))

    if not entries:
        print("No valid timetable entries.")
        return

    schedule = [(g["day"], sorted(g["classes"])) for g in entries.values()]
    total_classes = sum(len(classes) for _, classes in schedule)
    print(f"\nTotal classes: {total_classes}")

    summary_lines = []

    for day, classes in schedule:
        print(f"\n{day} — {len(classes)} classes")
        summary_lines.append(f"{day}:")

        for _, _, start, end, subject in classes:
            print(f"  {start}-{end}: {subject}")
            summary_lines.append(f"  {start}-{end} {subject}")

        for i in range(1, len(classes)):
            previous, current = classes[i - 1], classes[i]
            gap = current[0] - previous[1]
            if gap > 0:
                print(f"  Free period: {gap} minutes "
                      f"between {previous[4]} and {current[4]}")
                summary_lines.append(
                    f"  Free period of {gap} minutes between "
                    f"{previous[4]} and {current[4]}"
                )

    if client and yes_no("\nGet AI analysis of this timetable? (y/N): "):
        ask_gemini("\n".join(summary_lines), system=TIMETABLE_SYSTEM)
    elif not client:
        print("\n(Add GEMINI_API_KEY to .env to enable AI analysis.)")


# --------------------------------------------------------------- 4. Gemini
def ask_gemini(prompt, system=None):
    if not client:
        print("\nGemini API key missing. Configure your .env file.")
        return

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        print("\nGemini AI:")
        line()
        print(response.text or "No response received.")
        line()

    except Exception as error:
        print("\nGemini request failed.")
        print("Check internet, API key, model access and API quota.")
        print(f"Details: {error}")


def chatbot():
    line()
    print("COLLEGE AI CHATBOT")
    print("Type 'back' to return to the main menu.")

    if not client:
        print("\nGemini API key missing. Configure your .env file.")
        return

    # A chat session remembers earlier messages, so follow-ups work.
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=CHATBOT_SYSTEM),
    )

    while True:
        question = input("\nYou: ").strip()

        if question.lower() == "back":
            break
        if not question:
            continue

        try:
            response = chat.send_message(question)
            print("\nGemini AI:")
            line()
            print(response.text or "No response received.")
            line()
        except Exception as error:
            print("\nGemini request failed.")
            print("Check internet, API key, model access and API quota.")
            print(f"Details: {error}")


# ---------------------------------------------------------------- Main menu
def main():
    print("\n===================================")
    print("      COLLEGE AI ASSISTANT")
    print("===================================")

    if not client:
        print("Gemini key not configured. Local calculators still work.")

    while True:
        print("\n1. Attendance Calculator")
        print("2. Marks Calculator")
        print("3. Timetable Analysis")
        print("4. Gemini AI Chatbot")
        print("5. Exit")

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            attendance_calculator()
        elif choice == "2":
            marks_calculator()
        elif choice == "3":
            timetable_analyzer()
        elif choice == "4":
            chatbot()
        elif choice == "5":
            print("Exiting College AI Assistant.")
            break
        else:
            print("Invalid option. Choose 1-5.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting College AI Assistant.")
