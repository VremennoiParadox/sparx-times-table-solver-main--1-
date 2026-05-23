from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json
import csv

HISTORY_DIR = Path.home() / ".sparx_pro"
HISTORY_FILE = HISTORY_DIR / "history.json"


@dataclass
class QuestionRecord:
    expression: str
    answer: str
    elapsed_ms: int
    confidence: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SessionRecord:
    id: str
    start_time: str
    end_time: Optional[str]
    target_rounds: int
    completed_rounds: int
    questions: List[QuestionRecord] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if not self.end_time:
            return 0.0
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        return (end - start).total_seconds()

    @property
    def questions_per_minute(self) -> float:
        dur = self.duration_seconds
        if dur == 0:
            return 0.0
        return self.completed_rounds / dur * 60

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Expression", "Answer", "Time (ms)", "Confidence", "Timestamp"])
            for q in self.questions:
                w.writerow([q.expression, q.answer, q.elapsed_ms, f"{q.confidence:.2f}", q.timestamp])


class HistoryManager:
    def __init__(self):
        self.sessions: List[SessionRecord] = []
        self._load()

    def _load(self) -> None:
        if not HISTORY_FILE.exists():
            return
        try:
            data = json.loads(HISTORY_FILE.read_text())
            for s in data:
                questions = [QuestionRecord(**q) for q in s.pop("questions", [])]
                self.sessions.append(SessionRecord(**s, questions=questions))
        except Exception:
            pass

    def save(self) -> None:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps([asdict(s) for s in self.sessions], indent=2))

    def add_session(self, session: SessionRecord) -> None:
        self.sessions.append(session)
        self.save()

    def get_recent(self, n: int = 50) -> List[SessionRecord]:
        return sorted(self.sessions, key=lambda s: s.start_time, reverse=True)[:n]

    def total_questions(self) -> int:
        return sum(s.completed_rounds for s in self.sessions)

    def lifetime_best_rate(self) -> float:
        rates = [s.questions_per_minute for s in self.sessions if s.duration_seconds > 5]
        return max(rates) if rates else 0.0
