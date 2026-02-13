from datetime import datetime, timezone

import discord


class MemberProfileService:
    TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
        "データベース": ("database", "db", "データベース"),
        "API": ("api", "integration", "連携"),
        "タスク管理": ("task", "todo", "タスク"),
        "自動化": ("automation", "automate", "自動化"),
        "テンプレート": ("template", "テンプレ", "テンプレート"),
        "PKM": ("pkm", "second brain", "知識管理"),
        "Notion関数": ("formula", "関数", "数式"),
    }

    def build_realtime_profile(
        self,
        message: discord.Message,
        stats: dict[str, object],
        recent_posts: list[str],
        now: datetime,
    ) -> dict[str, object]:
        joined_at = getattr(message.author, "joined_at", None)
        if isinstance(joined_at, datetime) and joined_at.tzinfo is None:
            joined_at = joined_at.replace(tzinfo=timezone.utc)

        total_posts = int(stats.get("total_posts", 0))
        total_post_length = int(stats.get("total_post_length", 0))
        avg_post_length = (total_post_length / total_posts) if total_posts else 0
        hours_since_join = 0.0
        if isinstance(joined_at, datetime):
            hours_since_join = max(0.0, (now - joined_at).total_seconds() / 3600.0)

        post_frequency = 0.0
        if hours_since_join > 0:
            post_frequency = total_posts / (hours_since_join / 24.0)

        roles = getattr(message.author, "roles", [])
        role_names: list[str] = []
        for role in roles:
            role_name = getattr(role, "name", None)
            if isinstance(role_name, str) and role_name != "@everyone":
                role_names.append(role_name)

        combined_text = " ".join(recent_posts)
        topics = self._extract_topics(combined_text)
        skill_level = self._estimate_skill_level(total_posts, combined_text)
        style = self._estimate_style(recent_posts)
        recent_summary = self._recent_summary(recent_posts)
        days_since_last_post = 0
        last_active_at = now

        return {
            "display_name": getattr(message.author, "display_name", message.author.name),
            "avatar_url": str(getattr(message.author.display_avatar, "url", "")),
            "joined_at": joined_at,
            "roles": role_names,
            "stats": {
                "total_posts": total_posts,
                "active_channels": list((stats.get("active_channels", {}) or {}).keys()),
                "active_hours": stats.get("active_hours", {}),
                "avg_post_length": round(avg_post_length, 2),
                "post_frequency": round(post_frequency, 3),
                "reaction_given_count": 0,
                "reaction_received_count": 0,
            },
            "interests": {
                "topics": topics,
                "estimated_skill_level": skill_level,
                "style": style,
            },
            "context": {
                "recent_posts_summary": recent_summary,
                "current_context": recent_posts[-1] if recent_posts else "",
                "last_active_at": last_active_at,
                "days_since_last_post": days_since_last_post,
            },
            "relationships": {
                "frequent_interactions": [],
                "helped_by": [],
                "helped_others": [],
            },
            "outreach": {
                "last_outreach_at": None,
                "outreach_count": 0,
            },
            "updated_at": now,
        }

    def _extract_topics(self, text: str) -> list[str]:
        lowered = text.lower()
        topics: list[str] = []
        for label, keys in self.TOPIC_KEYWORDS.items():
            if any(key in lowered for key in keys):
                topics.append(label)
        return topics[:8]

    def _estimate_skill_level(self, total_posts: int, text: str) -> str:
        lowered = text.lower()
        if total_posts >= 40 and ("api" in lowered or "formula" in lowered):
            return "advanced"
        if total_posts >= 10:
            return "intermediate"
        return "beginner"

    def _estimate_style(self, posts: list[str]) -> str:
        if not posts:
            return "ROM専"
        joined = "\n".join(posts)
        question_marks = joined.count("?") + joined.count("？")
        if question_marks >= max(1, len(posts) // 2):
            return "質問多め"
        if len(posts) >= 3 and all(len(p) < 8 for p in posts):
            return "リアクション派"
        return "共有多め"

    def _recent_summary(self, posts: list[str]) -> str:
        if not posts:
            return ""
        trimmed = [p.strip().replace("\n", " ") for p in posts[-3:]]
        return " / ".join(trimmed)[:300]
