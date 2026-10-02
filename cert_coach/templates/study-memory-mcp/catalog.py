"""Load and validate the versioned SAA-C03 concept catalog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import os

SUPPORTED_EXAM_CODES = {"SAA-C03", "CLF-C02", "AIF-C01"}


def resolve_catalog_path() -> Path:
    """Find the concept catalog for the workspace, falling back to SAA-C03."""
    env_path = os.environ.get("STUDY_CATALOG_PATH")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file():
            return p

    workspace_root = Path(__file__).resolve().parents[1]
    docs_dir = workspace_root / "docs"

    config_file = workspace_root / ".cert-coach.json"
    if config_file.is_file():
        try:
            with config_file.open(encoding="utf-8") as f:
                data = json.load(f)
            exam = data.get("exam", "").lower()
            if exam:
                candidate = docs_dir / f"{exam}-concept-catalog.json"
                if candidate.is_file():
                    return candidate
        except Exception:
            pass

    if docs_dir.is_dir():
        catalogs = list(docs_dir.glob("*-concept-catalog.json"))
        if catalogs:
            for c in catalogs:
                if "saa-c03" in c.name.lower():
                    return c
            return catalogs[0]

    return docs_dir / "saa-c03-concept-catalog.json"


CATALOG_PATH = resolve_catalog_path()


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Return the validated catalog shared by persistence and MCP tools."""
    catalog_file_path = resolve_catalog_path() if not CATALOG_PATH.is_file() else CATALOG_PATH
    with catalog_file_path.open(encoding="utf-8") as catalog_file:
        catalog: dict[str, Any] = json.load(catalog_file)

    if catalog.get("schema_version") != "1.0":
        raise RuntimeError("Unsupported concept catalog schema version")
    exam_code = catalog.get("exam_code")
    if not exam_code or not isinstance(exam_code, str):
        raise RuntimeError("Concept catalog must specify a valid exam_code")

    domains = catalog.get("domains")
    if not isinstance(domains, list) or not domains:
        raise RuntimeError("Concept catalog must define domains")
    if sum(domain.get("weight", 0) for domain in domains) != 100:
        raise RuntimeError("Concept catalog domain weights must total 100")

    domain_ids: set[str] = set()
    task_ids: set[str] = set()
    topic_ids: set[str] = set()
    for domain in domains:
        domain_id = domain.get("id")
        if not isinstance(domain_id, str) or domain_id in domain_ids:
            raise RuntimeError("Concept catalog domain IDs must be unique strings")
        domain_ids.add(domain_id)
        tasks = domain.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            raise RuntimeError(f"Concept catalog domain {domain_id} must define tasks")
        for task in tasks:
            task_id = task.get("id")
            if not isinstance(task_id, str) or task_id in task_ids:
                raise RuntimeError("Concept catalog task IDs must be unique strings")
            task_ids.add(task_id)
            topics = task.get("topics")
            if not isinstance(topics, list) or not topics:
                raise RuntimeError(f"Concept catalog task {task_id} must define topics")
            for topic in topics:
                topic_id = topic.get("id")
                if not isinstance(topic_id, str) or topic_id in topic_ids:
                    raise RuntimeError("Concept catalog topic IDs must be globally unique strings")
                topic_ids.add(topic_id)
    return catalog


def catalog_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build domain, task, and topic lookup maps with parent relationships."""
    domains: dict[str, dict[str, Any]] = {}
    tasks: dict[str, dict[str, Any]] = {}
    topics: dict[str, dict[str, Any]] = {}
    for domain in load_catalog()["domains"]:
        domains[domain["id"]] = {
            "id": domain["id"],
            "name": domain["name"],
            "weight": domain["weight"],
            "official_reference": domain["official_reference"],
            "task_ids": [task["id"] for task in domain["tasks"]],
        }
        for task in domain["tasks"]:
            tasks[task["id"]] = {
                **task,
                "domain": domain["id"],
                "topic_ids": [topic["id"] for topic in task["topics"]],
            }
            for topic in task["topics"]:
                topics[topic["id"]] = {**topic, "domain": domain["id"], "task_id": task["id"]}
    return domains, tasks, topics


DOMAINS, TASKS, TOPICS = catalog_maps()
