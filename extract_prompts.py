#!/usr/bin/env python3
"""Extract prompt templates from all 18 KruppAI skill files and write to CSV.

Reads each skill .py file, extracts the system_prompt and user message
template from build_prompt(), and writes a Google-Sheets-compatible CSV.
"""

import ast
import csv
import re
import textwrap
from pathlib import Path

# Ordered list of skill files matching skill numbers 1-18
SKILLS = [
    {
        "number": 1,
        "file": "daily_report.py",
        "name": "Daily Field Report",
        "phase": 1,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 2,
        "file": "rfi_generator.py",
        "name": "RFI Generator",
        "phase": 1,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 3,
        "file": "meeting_minutes.py",
        "name": "Meeting Minutes",
        "phase": 1,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 4,
        "file": "client_update.py",
        "name": "Client Update Letter",
        "phase": 1,
        "model": "Sonnet",
        "output_format": "Markdown text",
    },
    {
        "number": 5,
        "file": "safety_talk.py",
        "name": "Toolbox Safety Talk",
        "phase": 1,
        "model": "Sonnet",
        "output_format": "Markdown text",
    },
    {
        "number": 6,
        "file": "punch_list.py",
        "name": "Punch List Generator",
        "phase": 1,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 7,
        "file": "estimate_reviewer.py",
        "name": "Estimate Reviewer",
        "phase": 2,
        "model": "Opus",
        "output_format": "JSON",
    },
    {
        "number": 8,
        "file": "bid_comparison.py",
        "name": "Bid Comparison",
        "phase": 2,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 9,
        "file": "change_order.py",
        "name": "Change Order Builder",
        "phase": 2,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 10,
        "file": "schedule_variance.py",
        "name": "Schedule Variance Analyzer",
        "phase": 2,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 11,
        "file": "submittal_tracker.py",
        "name": "Submittal Tracker",
        "phase": 2,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 12,
        "file": "contract_checker.py",
        "name": "Contract & Insurance Checker",
        "phase": 2,
        "model": "Opus",
        "output_format": "JSON",
    },
    {
        "number": 13,
        "file": "proposal_generator.py",
        "name": "Proposal Generator",
        "phase": 3,
        "model": "Opus",
        "output_format": "Section-break text",
    },
    {
        "number": 14,
        "file": "budget_forecaster.py",
        "name": "Budget Forecaster",
        "phase": 3,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 15,
        "file": "closeout_assembler.py",
        "name": "Closeout Assembler",
        "phase": 3,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 16,
        "file": "lessons_learned.py",
        "name": "Lessons Learned",
        "phase": 3,
        "model": "Sonnet",
        "output_format": "JSON",
    },
    {
        "number": 17,
        "file": "case_study.py",
        "name": "Case Study Generator",
        "phase": 3,
        "model": "Sonnet",
        "output_format": "Section-break text",
    },
    {
        "number": 18,
        "file": "incident_report.py",
        "name": "Incident Report",
        "phase": 3,
        "model": "Sonnet",
        "output_format": "JSON",
    },
]

SKILLS_DIR = Path(__file__).parent / "kruppai" / "skills"
OUTPUT_CSV = Path(__file__).parent / "skill_prompts.csv"


def extract_system_prompt_from_source(source: str) -> str:
    """Extract the system_prompt f-string literal from the build_prompt method source code.

    Strategy: Find the assignment `system_prompt = f\"\"\"...\"\"\"` in the source and
    extract the raw template text, preserving f-string placeholders as-is.
    """
    # Pattern 1: system_prompt = f"""..."""  (triple-quoted f-string)
    # We need to find system_prompt assignment and capture everything until the closing triple quote
    patterns = [
        # f-string triple double quotes
        r'system_prompt\s*=\s*f"""(.*?)"""',
        # f-string triple single quotes
        r"system_prompt\s*=\s*f'''(.*?)'''",
        # regular triple double quotes
        r'system_prompt\s*=\s*"""(.*?)"""',
        # regular triple single quotes
        r"system_prompt\s*=\s*'''(.*?)'''",
    ]

    for pattern in patterns:
        match = re.search(pattern, source, re.DOTALL)
        if match:
            return match.group(1).strip()

    return "EXTRACTION FAILED"


def extract_user_prompt_template(source: str) -> str:
    """Extract the user message template from the build_prompt method.

    The user prompt is typically constructed as a user_content variable,
    or directly in the return statement.
    """
    # Look for user_content assignment patterns
    # Pattern: user_content = f"..." or user_content = "..."

    # First try to find the full user_content construction block
    # Find from first user_content assignment to the return statement
    lines = source.split('\n')
    in_build_prompt = False
    user_content_lines = []
    capturing = False
    return_found = False

    for line in lines:
        if 'def build_prompt' in line:
            in_build_prompt = True
            continue

        if in_build_prompt:
            stripped = line.strip()

            # Detect user_content assignment
            if 'user_content' in stripped and ('=' in stripped) and not stripped.startswith('#'):
                capturing = True

            if capturing and not return_found:
                user_content_lines.append(line)

            # Stop at the return statement
            if stripped.startswith('return [') or stripped.startswith('return['):
                return_found = True
                # Also capture the return block
                if not capturing:
                    # No user_content variable -- the content is inline in the return
                    pass

            # Detect next def (end of build_prompt)
            if stripped.startswith('def ') and 'build_prompt' not in stripped:
                break

    if user_content_lines:
        return '\n'.join(user_content_lines).strip()

    # Fallback: try to find the return statement content directly
    return _extract_return_content(source)


def _extract_return_content(source: str) -> str:
    """Extract the user message content from the return statement of build_prompt."""
    # Find the build_prompt method and its return
    in_build_prompt = False
    indent_level = None
    return_block = []
    capturing_return = False
    brace_depth = 0

    for line in source.split('\n'):
        if 'def build_prompt' in line:
            in_build_prompt = True
            indent_level = len(line) - len(line.lstrip())
            continue

        if in_build_prompt:
            stripped = line.strip()

            if capturing_return:
                return_block.append(line)
                brace_depth += line.count('[') - line.count(']')
                if brace_depth <= 0:
                    break

            if stripped.startswith('return'):
                capturing_return = True
                return_block.append(line)
                brace_depth += line.count('[') - line.count(']')
                if brace_depth <= 0:
                    break

            # Detect next method at same or lesser indent
            current_indent = len(line) - len(line.lstrip()) if stripped else 999
            if stripped.startswith('def ') and current_indent <= indent_level + 4:
                if 'build_prompt' not in stripped:
                    break

    return '\n'.join(return_block).strip() if return_block else "EXTRACTION FAILED"


def extract_build_prompt_method(source: str) -> str:
    """Extract just the build_prompt method source code."""
    lines = source.split('\n')
    result = []
    in_method = False
    method_indent = None

    for line in lines:
        stripped = line.strip()

        if 'def build_prompt' in line:
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            result.append(line)
            continue

        if in_method:
            if stripped == '':
                result.append(line)
                continue

            current_indent = len(line) - len(line.lstrip())

            # If we encounter a new top-level def at the same or less indentation, stop
            if stripped.startswith('def ') and current_indent <= method_indent:
                break

            result.append(line)

    return '\n'.join(result)


def extract_role_line(system_prompt: str) -> str:
    """Extract the first line or two that establish the AI's role."""
    lines = system_prompt.strip().split('\n')
    role_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            break
        role_lines.append(stripped)
        # Usually just 1-2 lines establishing the role
        if len(role_lines) >= 2:
            break
    return '\n'.join(role_lines)


def extract_json_schema(system_prompt: str, output_format: str) -> str:
    """Extract the JSON output schema from the system prompt if applicable.

    Uses brace-depth counting on the doubled {{ / }} delimiters to find the
    complete outermost JSON object that appears after the OUTPUT FORMAT marker.
    """
    if output_format != "JSON":
        return "N/A - free text"

    # Find the start of the output format / schema section
    output_section_start = -1
    for keyword in ["OUTPUT FORMAT", "Return JSON", "Return a JSON object"]:
        idx = system_prompt.find(keyword)
        if idx >= 0:
            output_section_start = idx
            break

    if output_section_start < 0:
        return "N/A - schema embedded in instructions"

    search_text = system_prompt[output_section_start:]

    # Find the first {{ which starts the JSON schema
    first_brace = search_text.find("{{")
    if first_brace < 0:
        return "N/A - schema embedded in instructions"

    # Count brace depth to find the matching closing }}
    # Each {{ increments depth by 1, each }} decrements by 1
    text = search_text[first_brace:]
    depth = 0
    i = 0
    schema_end = -1

    while i < len(text):
        if i + 1 < len(text) and text[i] == '{' and text[i + 1] == '{':
            depth += 1
            i += 2
        elif i + 1 < len(text) and text[i] == '}' and text[i + 1] == '}':
            depth -= 1
            i += 2
            if depth == 0:
                schema_end = i
                break
        else:
            i += 1

    if schema_end < 0:
        # Fallback: grab from first {{ to last }}
        last_brace = text.rfind("}}")
        if last_brace >= 0:
            schema_end = last_brace + 2

    if schema_end > 0:
        raw_schema = text[:schema_end]
        # Convert doubled braces back to single for readability
        schema = raw_schema.replace('{{', '{').replace('}}', '}')
        return schema.strip()

    return "N/A - schema embedded in instructions"


def process_skill(skill_info: dict) -> dict:
    """Process a single skill file and extract prompt information."""
    file_path = SKILLS_DIR / skill_info["file"]
    source = file_path.read_text(encoding="utf-8")

    # Extract build_prompt method
    build_prompt_source = extract_build_prompt_method(source)

    # Extract system prompt template
    system_prompt = extract_system_prompt_from_source(build_prompt_source)

    # Extract role line from system prompt
    role_line = extract_role_line(system_prompt)

    # Extract user prompt template
    user_prompt = extract_user_prompt_template(build_prompt_source)

    # Extract JSON schema
    json_schema = extract_json_schema(system_prompt, skill_info["output_format"])

    return {
        "skill_number": skill_info["number"],
        "skill_name": skill_info["name"],
        "phase": skill_info["phase"],
        "model": skill_info["model"],
        "output_format": skill_info["output_format"],
        "system_prompt_role": role_line,
        "system_prompt_full": system_prompt,
        "user_prompt_template": user_prompt,
        "output_json_schema": json_schema,
    }


def main() -> None:
    """Main entry point: process all skills and write CSV."""
    rows = []

    for skill_info in SKILLS:
        print(f"Processing skill #{skill_info['number']}: {skill_info['name']}...")
        try:
            row = process_skill(skill_info)
            rows.append(row)
            print(f"  OK - system prompt: {len(row['system_prompt_full'])} chars, "
                  f"user prompt: {len(row['user_prompt_template'])} chars")
        except Exception as e:
            print(f"  ERROR: {e}")
            rows.append({
                "skill_number": skill_info["number"],
                "skill_name": skill_info["name"],
                "phase": skill_info["phase"],
                "model": skill_info["model"],
                "output_format": skill_info["output_format"],
                "system_prompt_role": f"ERROR: {e}",
                "system_prompt_full": f"ERROR: {e}",
                "user_prompt_template": f"ERROR: {e}",
                "output_json_schema": f"ERROR: {e}",
            })

    # Write CSV with UTF-8 BOM for Google Sheets
    fieldnames = [
        "skill_number",
        "skill_name",
        "phase",
        "model",
        "output_format",
        "system_prompt_role",
        "system_prompt_full",
        "user_prompt_template",
        "output_json_schema",
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV written to: {OUTPUT_CSV}")
    print(f"Total skills: {len(rows)}")

    # Verify
    with open(OUTPUT_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            count += 1
            sys_len = len(row["system_prompt_full"])
            user_len = len(row["user_prompt_template"])
            schema_preview = row["output_json_schema"][:60]
            print(f"  Row {count}: #{row['skill_number']} {row['skill_name']:<35} "
                  f"sys={sys_len:>5} user={user_len:>4} schema={schema_preview}...")
        print(f"  Verified {count} rows in CSV")


if __name__ == "__main__":
    main()
