"""Daily Field Report Generator — Skill #1.

Transforms a superintendent's rough field notes into a professional
daily field report with weather data, workforce counts, and structured sections.

This is the most commonly used skill — one report per project per day.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from kruppai.core.api_client import parse_claude_json
from kruppai.core.context_manager import ProjectContext
from kruppai.core.database import get_db, get_next_number
from kruppai.core.output_formatter import (
    DocumentContent,
    ProjectInfo,
    Section,
    TableData,
)
from kruppai.skills.base import BaseSkill


def fetch_weather(lat: float, lng: float, date_str: str) -> dict:
    """Fetch historical weather from Open-Meteo API (free, no key needed).

    Args:
        lat: Latitude of the project site.
        lng: Longitude of the project site.
        date_str: Date in YYYY-MM-DD format.

    Returns:
        Weather dict with keys: high_f, low_f, conditions, precipitation, wind.
        Empty dict if API fails.
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/Chicago",
            "start_date": date_str,
            "end_date": date_str,
        }
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        weather_code = (daily.get("weather_code") or [None])[0]
        conditions = _weather_code_to_text(weather_code)

        return {
            "high_f": (daily.get("temperature_2m_max") or [None])[0],
            "low_f": (daily.get("temperature_2m_min") or [None])[0],
            "conditions": conditions,
            "precipitation": f"{(daily.get('precipitation_sum') or [0])[0]:.2f} in",
            "wind": f"{(daily.get('wind_speed_10m_max') or [0])[0]:.0f} mph",
        }
    except Exception:
        return {}


def _weather_code_to_text(code: int | None) -> str:
    """Convert WMO weather code to human-readable text."""
    if code is None:
        return "Unknown"
    mapping = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return mapping.get(code, "Unknown")


class DailyReportSkill(BaseSkill):
    """Generate professional daily field reports from rough notes."""

    skill_name = "daily_report"
    display_name = "Daily Field Report"
    description = "Transform field notes into a professional daily report"
    phase = 1
    default_model = "sonnet"
    output_formats = ["docx"]

    def validate_input(self, **kwargs: object) -> dict:
        """Validate daily report input.

        Required: project (code), notes (text or file path).
        Optional: date, weather_override, output_dir.
        """
        project_code = kwargs.get("project")
        notes = kwargs.get("notes")
        report_date = kwargs.get("date")
        weather_override = kwargs.get("weather_override")

        if not project_code:
            raise ValueError("Project code is required. Use --project or -p.")
        if not notes:
            raise ValueError("Field notes are required. Use --notes or -n.")

        # Notes can be a file path
        notes_str = str(notes)
        notes_path = Path(notes_str)
        if notes_path.exists() and notes_path.is_file():
            notes_str = notes_path.read_text(encoding="utf-8")

        if len(notes_str.strip()) < 20:
            raise ValueError(
                "Field notes must be at least 20 characters. "
                "A real daily report needs substance."
            )

        # Validate date
        if report_date:
            try:
                parsed_date = datetime.strptime(str(report_date), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(
                    f"Invalid date format: '{report_date}'. Use YYYY-MM-DD."
                )
            if parsed_date > date.today():
                raise ValueError("Report date cannot be in the future.")
            if parsed_date < date.today() - timedelta(days=30):
                raise ValueError("Report date cannot be more than 30 days in the past.")
        else:
            parsed_date = date.today()

        # Look up project
        context = self.context_manager.load_by_code(str(project_code))
        project_id = context.project["id"]

        return {
            "project_id": project_id,
            "project_code": str(project_code),
            "notes": notes_str,
            "report_date": parsed_date.isoformat(),
            "weather_override": weather_override,
        }

    def build_prompt(
        self, validated: dict, context: ProjectContext | None
    ) -> list[dict]:
        """Build the Claude API messages for daily report generation."""
        project = context.project if context else {}
        company = context.company if context else {}

        # Format subcontractor list
        sub_list = ""
        if context and context.subcontractors:
            lines = []
            for sub in context.subcontractors:
                lines.append(
                    f"- {sub['company_name']} ({sub['trade']}): "
                    f"{sub.get('scope_description', 'N/A')}"
                )
            sub_list = "\n".join(lines)
        else:
            sub_list = "No subcontractors listed for this project."

        # Get writing standards from knowledge base
        writing_standards = self.knowledge_base.load_file("writing_standards") or ""
        company_profile = self.knowledge_base.load_file("company_profile") or ""

        # Find PM and super names
        pm_name = "N/A"
        super_name = "N/A"
        if context:
            for member in context.team:
                if member.get("project_role") == "project_manager":
                    pm_name = f"{member['first_name']} {member['last_name']}"
                elif member.get("project_role") == "superintendent":
                    super_name = f"{member['first_name']} {member['last_name']}"

        # Weather data
        weather_info = ""
        if validated.get("weather_override"):
            weather_info = f"WEATHER (manual): {validated['weather_override']}"
        elif (
            project.get("latitude")
            and project.get("longitude")
            and self.settings.weather_enabled
        ):
            weather = fetch_weather(
                project["latitude"],
                project["longitude"],
                validated["report_date"],
            )
            if weather:
                weather_info = (
                    f"WEATHER DATA (auto-fetched):\n"
                    f"High: {weather.get('high_f', 'N/A')}°F, "
                    f"Low: {weather.get('low_f', 'N/A')}°F\n"
                    f"Conditions: {weather.get('conditions', 'N/A')}\n"
                    f"Precipitation: {weather.get('precipitation', 'N/A')}\n"
                    f"Wind: {weather.get('wind', 'N/A')}"
                )

        contract_display = "N/A"
        if project.get("current_contract_cents"):
            contract_display = f"${project['current_contract_cents'] / 100:,.2f}"

        system_prompt = f"""You are a professional construction daily report writer for {company.get('name', 'Krupp General Contractors')}, a general contractor.

Your task: Transform the superintendent's rough field notes into a structured, professional daily field report.

COMPANY CONTEXT:
{company_profile}

PROJECT CONTEXT:
Project: {project.get('name', 'N/A')} ({project.get('project_code', 'N/A')})
Client: {project.get('client_name', 'N/A')}
Location: {project.get('address', 'N/A')}, {project.get('city', '')}, {project.get('state', '')}
Contract Value: {contract_display}
Percent Complete: {project.get('current_percent_complete', 0)}%
Project Manager: {pm_name}
Superintendent: {super_name}

SUBCONTRACTORS ON PROJECT:
{sub_list}

WRITING STANDARDS:
{writing_standards}

INSTRUCTIONS:
1. Organize the notes into these sections (skip any section with no relevant data):
   - WORK PERFORMED TODAY: Describe each activity professionally. Group by trade/area. Use past tense, active voice. Include quantities where mentioned.
   - WORKFORCE: Extract headcount. If specific sub counts are mentioned, list them. Otherwise use the total.
   - MATERIALS DELIVERED: List any materials received on site.
   - EQUIPMENT ON SITE: Note any equipment mentioned.
   - WEATHER & DELAYS: Report weather conditions and any delays with duration and cause.
   - SAFETY: Note safety observations, incidents, or compliance items.
   - VISITORS: List any visitors mentioned.
   - ISSUES & CONCERNS: Flag anything that needs attention.
   - UPCOMING WORK: Note any forward-looking items mentioned.

2. CRITICAL RULES:
   - Do NOT invent information. Only report what's in the notes.
   - If something is ambiguous, include it with [VERIFY] tag.
   - Use professional construction terminology but keep it clear.
   - Match subcontractor names to the project sub list when possible.
   - Keep descriptions concise but complete — a daily report is a legal record.
   - Numbers and quantities must be exact as stated in the notes.

3. OUTPUT FORMAT:
   Return a JSON object with these keys:
   {{
     "report_date": "YYYY-MM-DD",
     "weather": {{"high_f": null, "low_f": null, "conditions": "", "precipitation": "", "wind": ""}},
     "workforce": {{"krupp_workers": 0, "sub_workers": 0, "total": 0, "detail": [{{"company": "", "trade": "", "headcount": 0, "work_area": ""}}]}},
     "work_performed": "Professional narrative of work performed",
     "materials_delivered": ["item1", "item2"],
     "equipment_on_site": ["item1", "item2"],
     "visitors": ["name - company"],
     "delays": "Description of delays or 'None'",
     "safety_observations": "Safety notes",
     "issues": ["issue1", "issue2"],
     "upcoming_work": "Forward-looking items or 'None noted'"
   }}"""

        user_content = f"REPORT DATE: {validated['report_date']}\n"
        if weather_info:
            user_content += f"\n{weather_info}\n"
        user_content += f"\nFIELD NOTES:\n{validated['notes']}"

        return [
            {"role": "user", "content": user_content},
        ]

    def format_output(
        self,
        response: str,
        context: ProjectContext | None,
        validated: dict,
    ) -> Path:
        """Format the daily report as a branded DOCX."""
        data = parse_claude_json(response)

        project = context.project if context else {}
        project_info = ProjectInfo(
            project_code=validated["project_code"],
            name=project.get("name", ""),
            client_name=project.get("client_name", ""),
            address=project.get("address", ""),
        )

        # Get report number
        with get_db(self.settings) as conn:
            report_number = get_next_number(
                conn, "daily_reports", validated["project_id"], "report_number"
            )

        # Build weather summary
        weather = data.get("weather", {})
        weather_summary = ""
        if weather.get("conditions"):
            parts = [weather["conditions"]]
            if weather.get("high_f"):
                parts.append(f"High: {weather['high_f']}°F")
            if weather.get("low_f"):
                parts.append(f"Low: {weather['low_f']}°F")
            weather_summary = " | ".join(parts)

        # Header fields
        header_fields = {
            "Project": f"{project.get('name', '')} ({validated['project_code']})",
            "Report Date": validated["report_date"],
            "Report Number": str(report_number),
            "Weather": weather_summary or "Not recorded",
        }

        # Sections
        sections: list[Section] = []

        if data.get("work_performed"):
            sections.append(Section("Work Performed Today", data["work_performed"]))

        if data.get("delays") and data["delays"] != "None":
            sections.append(Section("Weather & Delays", data["delays"]))

        if data.get("safety_observations"):
            sections.append(
                Section("Safety Observations", data["safety_observations"])
            )

        materials = data.get("materials_delivered", [])
        if materials:
            sections.append(
                Section("Materials Delivered", "\n".join(f"- {m}" for m in materials))
            )

        equipment = data.get("equipment_on_site", [])
        if equipment:
            sections.append(
                Section("Equipment On Site", "\n".join(f"- {e}" for e in equipment))
            )

        visitors = data.get("visitors", [])
        if visitors:
            sections.append(
                Section("Visitors", "\n".join(f"- {v}" for v in visitors))
            )

        issues = data.get("issues", [])
        if issues:
            sections.append(
                Section("Issues & Concerns", "\n".join(f"- {i}" for i in issues))
            )

        if data.get("upcoming_work") and data["upcoming_work"] != "None noted":
            sections.append(Section("Upcoming Work", data["upcoming_work"]))

        # Workforce table
        tables: list[TableData] = []
        workforce = data.get("workforce", {})
        workforce_detail = workforce.get("detail", [])
        if workforce_detail:
            rows = []
            for entry in workforce_detail:
                rows.append([
                    str(entry.get("company", "")),
                    str(entry.get("trade", "")),
                    str(entry.get("headcount", "")),
                    str(entry.get("work_area", "")),
                ])
            # Add total row
            total = workforce.get("total", 0)
            rows.append(["TOTAL", "", str(total), ""])
            tables.append(
                TableData(
                    headers=["Company", "Trade", "Headcount", "Work Area"],
                    rows=rows,
                    title="Workforce",
                )
            )

        content = DocumentContent(
            title="Daily Field Report",
            date=validated["report_date"],
            header_fields=header_fields,
            sections=sections,
            tables=tables,
        )

        output_path = self.formatter.create_docx(
            content, project_info, skill_name=self.skill_name
        )

        # Persist to daily_reports table
        self._persist_daily_report(validated, data, report_number, output_path)

        return output_path

    def _persist_daily_report(
        self,
        validated: dict,
        data: dict,
        report_number: int,
        output_path: Path,
    ) -> None:
        """Save daily report data to the daily_reports table."""
        workforce = data.get("workforce", {})
        weather = data.get("weather", {})

        with get_db(self.settings) as conn:
            conn.execute(
                "INSERT INTO daily_reports "
                "(project_id, report_date, report_number, "
                "weather_high_f, weather_low_f, weather_conditions, "
                "krupp_workers, sub_workers, total_workers, "
                "raw_notes, work_performed, materials_delivered, "
                "equipment_on_site, visitors, delays, safety_observations, "
                "issues, workforce_detail, document_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    validated["project_id"],
                    validated["report_date"],
                    report_number,
                    weather.get("high_f"),
                    weather.get("low_f"),
                    weather.get("conditions"),
                    workforce.get("krupp_workers", 0),
                    workforce.get("sub_workers", 0),
                    workforce.get("total", 0),
                    validated["notes"],
                    data.get("work_performed", ""),
                    json.dumps(data.get("materials_delivered", [])),
                    json.dumps(data.get("equipment_on_site", [])),
                    json.dumps(data.get("visitors", [])),
                    data.get("delays", ""),
                    data.get("safety_observations", ""),
                    json.dumps(data.get("issues", [])),
                    json.dumps(workforce.get("detail", [])),
                    str(output_path),
                ),
            )
