from __future__ import annotations
from pathlib import Path
import json
import re
import yaml


class CapabilityRouter:
    """Deterministic first-pass intent/capability resolver for GUPPI.

    It does not execute tools. It produces a bounded route from the user/captain
    intent to registered modules, GUPPI skills, tools and a model policy. The
    route is stored in Mission State and becomes an allow-list for Control Master.
    """

    id = "capability-router"

    def __init__(self, registry, config_path: Path, audit=None, tools=None, topic_store=None):
        self.registry = registry
        self.config_path = Path(config_path)
        self.audit = audit
        self.tools = tools
        self.topic_store = topic_store
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        self.config = data.get("capability_router", {})
        if int(self.config.get("schema", 0)) != 1:
            raise ValueError("unsupported_capability_router_schema")

    @staticmethod
    def _norm(value):
        text = str(value or "").casefold()
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _score_profile(self, text, profile):
        score = 0
        matched = []
        for phrase in profile.get("phrases", []):
            p = self._norm(phrase)
            if p and self._matches(text, p):
                score += 4
                matched.append(phrase)
        for keyword in profile.get("keywords", []):
            k = self._norm(keyword)
            if not k:
                continue
            if " " in k:
                hit = k in text
            else:
                hit = bool(re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", text))
            if hit:
                score += 1
                matched.append(keyword)
        return score, matched

    @staticmethod
    def _matches(text, phrase):
        return bool(re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', text))

    def topic_catalog(self):
        catalog = {k: dict(v, id=k, status='built-in') for k, v in self.config.get('topics', {}).items()}
        if self.topic_store:
            catalog.update(self.topic_store.list())
        return catalog

    def _matched_intents(self, text):
        selection = self.config.get("selection", {})
        minimum = int(selection.get("minimum_intent_score", 1))
        limit = max(1, int(selection.get("max_intent_families", 3)))
        found = []
        for name, profile in self.config.get("intents", {}).items():
            score, matched = self._score_profile(text, profile)
            if score >= minimum:
                found.append({"id": name, "score": score, "matched": matched, "profile": profile})
        found.sort(key=lambda x: (-x["score"], x["id"]))
        return found[:limit]

    def _risk(self, text, matched):
        level = self.config.get("defaults", {}).get("risk_level", "low")
        reasons = []
        rank = {"low": 0, "medium": 1, "high": 2}
        for item in matched:
            candidate = item["profile"].get("risk_level", "low")
            if rank.get(candidate, 0) > rank.get(level, 0):
                level = candidate
        for candidate in ("high", "medium"):
            for signal in self.config.get("risk_signals", {}).get(candidate, []):
                if self._norm(signal) in text:
                    reasons.append(signal)
                    if rank[candidate] > rank.get(level, 0):
                        level = candidate
        return {"level": level, "signals": sorted(set(reasons)), "guard_required": level in {"medium", "high"}}

    def _skill_score(self, sid, skill, required, preferred, text):
        score = 0
        reasons = []
        caps = set(skill.get("capabilities", []))
        overlap = sorted(caps.intersection(required))
        if overlap:
            score += 3 * len(overlap)
            reasons.append("capabilities:" + ",".join(overlap))
        if sid in preferred:
            score += 100
            reasons.append("intent-preferred")
        trigger_hits = []
        for trigger in skill.get("triggers", []):
            if self._norm(trigger) and self._matches(text, self._norm(trigger)):
                score += 1
                trigger_hits.append(trigger)
        if trigger_hits:
            reasons.append("triggers:" + ",".join(trigger_hits[:4]))
        return score, reasons

    def _select_skills(self, required, preferred, text):
        limit = max(1, int(self.config.get("selection", {}).get("max_skills", 5)))
        selected = []
        for sid, meta in self.registry.skills.items():
            if not meta.get("enabled", True) or meta.get('data', {}).get('status', 'enabled') != 'enabled':
                continue
            skill = meta.get("data", {})
            # Shared capabilities alone must not drag unrelated workflows into
            # a route as the catalogue grows.
            if sid not in preferred and not any(self._norm(t) and self._matches(text, self._norm(t)) for t in skill.get('triggers', [])):
                continue
            score, reasons = self._skill_score(sid, skill, required, preferred, text)
            if score > 0:
                selected.append({
                    "id": sid,
                    "version": str(skill.get("version", meta.get("version", ""))),
                    "score": score,
                    "capabilities": skill.get("capabilities", []),
                    "tool_hints": skill.get("tool_hints", []),
                    "workflow": skill.get("workflow", []),
                    "execution_support": skill.get('execution_support', 'blueprint_only'),
                    "inputs": skill.get('inputs', []),
                    "outputs": skill.get('outputs', []),
                    "acceptance_criteria": skill.get('acceptance_criteria', []),
                    "boundaries": skill.get('boundaries', []),
                    "reason": reasons,
                })
        selected.sort(key=lambda x: (-x["score"], x["id"]))
        return selected[:limit]

    def _tool_state(self):
        return self.tools.list() if self.tools is not None else {}

    def _tool_score(self, tid, tool, required, preferred, skill_hints):
        score = 0
        reasons = []
        semantic = set(self.config.get("tool_semantic_capabilities", {}).get(tid, []))
        matched_caps = sorted(set(required).intersection(semantic))
        if matched_caps:
            score += 3 * len(matched_caps)
        if matched_caps:
            reasons.append("capabilities:" + ",".join(sorted(set(matched_caps))))
        if tid in preferred:
            score += 8
            reasons.append("intent-preferred")
        if tid in skill_hints:
            score += 6
            reasons.append("skill-hint")
        return score, reasons

    def _select_tools(self, required, preferred, skills):
        limit = max(1, int(self.config.get("selection", {}).get("max_tools", 6)))
        hints = []
        for skill in skills:
            hints.extend(skill.get("tool_hints", []))
        hints = set(hints)
        state = self._tool_state()
        selected, unavailable = [], []
        for tid, meta in self.registry.tools.items():
            if not meta.get("enabled", True):
                continue
            tool = meta.get("data", {})
            score, reasons = self._tool_score(tid, tool, required, set(preferred), hints)
            if score <= 0:
                continue
            live = state.get(tid, {})
            available = live.get("registered", True) and live.get("healthy", True)
            record = {
                "id": tid,
                "version": str(tool.get("version", meta.get("version", ""))),
                "score": score,
                "capabilities": tool.get("capabilities", []),
                "available": bool(available),
                "operations": live.get("operations", []),
                "reason": reasons,
            }
            if available:
                selected.append(record)
            else:
                unavailable.append(record)
        selected.sort(key=lambda x: (-x["score"], x["id"]))
        unavailable.sort(key=lambda x: (-x["score"], x["id"]))
        return selected[:limit], unavailable[:limit]

    def _select_modules(self, preferred):
        defaults = list(self.config.get("defaults", {}).get("modules", []))
        ids = []
        for mid in defaults + list(preferred):
            if mid in self.registry.modules and mid not in ids:
                ids.append(mid)
        return [{"id": mid, "version": str(self.registry.modules[mid]["data"].get("version", ""))} for mid in ids]

    def _model_policy(self, matched):
        policy = dict(self.config.get("defaults", {}).get("model_policy", {}))
        rank = {"general": 0, "reasoning": 1, "coding": 2, "runtime-management": 1}
        for item in matched:
            candidate = item["profile"].get("model_policy") or {}
            if candidate.get("required"):
                policy["required"] = True
            if rank.get(candidate.get("profile"), 0) >= rank.get(policy.get("profile"), 0):
                policy.update(candidate)
            elif candidate.get("local_first") is False:
                policy["local_first"] = False
        return policy

    def _blueprint(self, skills):
        steps = []
        seen = set()
        for skill in skills:
            for item in skill.get("workflow", []):
                key = json.dumps(item, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                out = dict(item)
                out["skill"] = skill["id"]
                steps.append(out)
        return steps

    def route(self, intent, objective=None, mission_class="S1", topic_hint=None):
        text = ' '.join(dict.fromkeys(self._norm(x) for x in [intent, objective] if x))
        matched = self._matched_intents(text)
        if not topic_hint:
            explicit = re.search(r'(?:thema|themenbereich|topic)\s*:\s*([^.;]{1,100})', text)
            if explicit: topic_hint = explicit.group(1).strip()
        topic_gaps, proposed_topics, custom_topics = [], [], []
        if self.topic_store:
            try:
                custom_topics = self.topic_store.match(text)
                greeting = bool(re.match(r'^(hallo|hello|hi|guten morgen|guten tag)(?:\s|$)', text))
                unknown = not matched and len(text.split()) >= 2 and not greeting
                hint_exists = topic_hint and any(t['label'].casefold() == str(topic_hint).strip().casefold() for t in custom_topics)
                if (topic_hint and not hint_exists) or (unknown and not custom_topics):
                    title = topic_hint or ' '.join(text.split()[:8])[:100]
                    draft = self.topic_store.propose(title, 'Themenlücke; passendes Skillset noch zu prüfen.',
                                                     text[:500], origin='router-gap')
                    proposed_topics.append(draft)
                    custom_topics.append(draft)
            except (ValueError, RuntimeError, OSError) as exc:
                topic_gaps.append({'type':'topic_store_unavailable', 'reason':str(exc)})
        elif topic_hint:
            topic_gaps.append({'type':'topic_store_unavailable', 'reason':'topic_store_not_configured'})
        if custom_topics:
            topic_gaps.append({'type':'topic_skillset_pending', 'ids':[t['id'] for t in custom_topics]})
        if not matched:
            matched = [{
                "id": "general",
                "score": 0,
                "matched": [],
                "profile": {
                    "required_capabilities": ["context_retrieval"],
                    "preferred_skills": ["knowledge-retrieval"],
                    "preferred_tools": [],
                    "preferred_modules": ["knowledge"],
                    "model_policy": self.config.get("defaults", {}).get("model_policy", {}),
                    "risk_level": "low",
                },
            }]

        required, preferred_skills, preferred_tools, preferred_modules, runtime_required = [], [], [], [], []
        for item in matched:
            p = item["profile"]
            for src, dest in [
                (p.get("required_capabilities", []), required),
                (p.get("preferred_skills", []), preferred_skills),
                (p.get("preferred_tools", []), preferred_tools),
                (p.get("preferred_modules", []), preferred_modules),
                (p.get('runtime_requirements', []), runtime_required),
            ]:
                for value in src:
                    if value not in dest:
                        dest.append(value)

        skills = self._select_skills(set(required), set(preferred_skills), text)
        for cap, signals in self.config.get('runtime_requirement_signals', {}).items():
            if any(self._matches(text, self._norm(signal)) for signal in signals) and cap not in runtime_required:
                runtime_required.append(cap)
        tools, unavailable = self._select_tools(set(required), preferred_tools, skills)
        modules = self._select_modules(preferred_modules)
        risk = self._risk(text, matched)
        if mission_class == "S2" and risk["level"] != "high":
            risk["level"] = "high"
            risk["guard_required"] = True
            risk["signals"].append("mission_class:S2")

        unresolved = list(topic_gaps)
        missing_skills = [sid for sid in preferred_skills if sid not in {s["id"] for s in skills}]
        if missing_skills:
            unresolved.append({"type": "missing_skill", "ids": missing_skills})
        missing_tools = [tid for tid in preferred_tools if tid not in {t["id"] for t in tools}]
        if missing_tools:
            unresolved.append({"type": "unavailable_tool", "ids": missing_tools})

        covered = set()
        for tool in tools:
            covered.update(self.config.get('tool_semantic_capabilities', {}).get(tool['id'], []))
        for module in modules:
            covered.update(self.config.get('module_semantic_capabilities', {}).get(module['id'], []))
        missing_caps = sorted(set(runtime_required) - covered)
        if missing_caps:
            unresolved.append({'type':'missing_runtime_capability', 'ids':missing_caps})
        topic_ids = []
        for item in matched:
            for tid in item['profile'].get('topics', []):
                if tid not in topic_ids: topic_ids.append(tid)
        topics = [dict(self.config['topics'][tid], id=tid, status='built-in') for tid in topic_ids]
        topics.extend(custom_topics)

        blueprint = self._blueprint(skills)
        live = self._tool_state()
        for step in blueprint:
            if step.get('tool') and step.get('tool') not in {t['id'] for t in tools}:
                unresolved.append({'type':'blueprint_tool_unavailable', 'ids':[step['tool']]})
            elif step.get('tool') and self.tools is not None and step.get('operation') not in live.get(step['tool'], {}).get('operations', []):
                unresolved.append({'type':'unsupported_blueprint_operation', 'tool':step['tool'], 'operation':step.get('operation')})

        route = {
            "schema": 1,
            "status": "resolved" if not unresolved else "resolved_with_gaps",
            "primary_intent": matched[0]["id"],
            "intent_families": [{"id": x["id"], "score": x["score"], "matched": x["matched"]} for x in matched],
            "required_capabilities": required,
            "runtime_requirements": runtime_required,
            "execution_requirements": {"allowed_execution_locations":["local"],"data_class":"internal","context_min_tokens":0},
            "topics": topics,
            "proposed_topics": proposed_topics,
            "execution_status": 'blueprint_only; parameter_binder_pending',
            "binding_support": self.config.get('execution_binders', {}).get(matched[0]['id']),
            "modules": modules,
            "skills": skills,
            "tools": tools,
            "unavailable_tools": unavailable,
            "model_policy": self._model_policy(matched),
            "risk": risk,
            "execution_blueprint": blueprint,
            "unresolved": unresolved,
            "enforce_tool_allowlist": bool(self.config.get("selection", {}).get("enforce_selected_tools", True)),
            "provenance": {"router": self.id, "config_version": str(self.config.get("version", ""))},
        }
        if self.audit:
            self.audit.append(
                "CAPABILITY_ROUTE_SELECTED",
                component=self.id,
                payload={
                    "primary_intent": route["primary_intent"],
                    "skills": [x["id"] for x in skills],
                    "tools": [x["id"] for x in tools],
                    "risk": risk["level"],
                },
            )
        return route

    def route_mission(self, mission):
        route = self.route(
            mission.get("captain_intent", {}).get("original", ""),
            mission.get("objective", {}).get("current", ""),
            mission.get("identity", {}).get("mission_class", "S1"),
        )
        return route

    def health(self):
        return bool(self.registry is not None and self.config.get("schema") == 1)
