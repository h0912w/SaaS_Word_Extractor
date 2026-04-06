"""
SaaS Word Whitelist — 명백한 SaaS 단어 목록

Step 4 스크리닝 단계에서 이 목록에 포함된 단어는
자동으로 accept하여 AI 판정을 건너뜁니다. 이를 통해 처리 시간을 단축합니다.

Whitelist 기준:
- SaaS 기능/브랜드로 명백히 사용되는 단어
- 의미의 모호함이 없는 확실한 단어
- 주요 tech/SaaS 플랫폼에서 통용적으로 사용되는 단어
"""

# 명백한 SaaS 기능어 (의미 확실한 단어만)
SAAS_FUNCTIONAL_WORDS = {
    # 핵심 SaaS 기능 동사
    "sync", "merge", "deploy", "track", "build", "parse", "render",
    "queue", "route", "stream", "crawl", "scrape", "index", "search",
    "filter", "sort", "group", "aggregate", "compute", "calculate",
    "validate", "verify", "authenticate", "authorize", "encrypt",
    "decrypt", "compress", "extract", "transform", "convert", "format",
    "cluster", "classify", "categorize", "rank", "score", "recommend",
    "predict", "forecast", "analyze", "visualize", "report", "monitor",
    "backup", "restore", "cache", "proxy", "bridge", "gateway",

    # 데이터/시스템 명사
    "api", "sdk", "cloud", "data", "code", "tech", "soft",
    "database", "dataset", "datatable", "file", "record", "field",
    "column", "row", "table", "index", "key", "value", "schema",
    "model", "type", "format", "template", "pattern", "config",
    "setting", "option", "parameter", "argument", "property",
    "attribute", "method", "function", "procedure", "routine",

    # 비즈니스/커머스 SaaS
    "payment", "invoice", "receipt", "order", "cart", "checkout",
    "shipment", "delivery", "inventory", "stock", "catalog",
    "product", "service", "subscription", "membership", "account",
    "profile", "user", "customer", "client", "partner", "vendor",
    "platform", "marketplace", "exchange", "auction", "bidding",
    "contract", "agreement", "terms", "policy", "invoice", "quote",
    "estimate", "proposal", "dashboard", "analytics", "metrics",
    "insights", "recommendation", "forecast", "prediction", "projection",

    # 시스템/인프라
    "server", "client", "host", "node", "cluster", "network",
    "router", "switch", "hub", "gateway", "firewall", "loadbalancer",
    "container", "pod", "service", "endpoint", "port", "protocol",
    "domain", "subdomain", "url", "uri", "link", "path", "route",

    # 개발/테스트
    "test", "debug", "build", "deploy", "release", "version",
    "commit", "push", "pull", "merge", "branch", "repository",
    "issue", "ticket", "task", "project", "workspace", "environment",

    # 보안/인증
    "login", "logout", "signin", "signout", "signup", "register",
    "password", "token", "session", "cookie", "auth", "permission",
    "role", "access", "grant", "revoke", "verify", "validate",
}

# 명백한 SaaS 브랜드형 (음성/이미지 확실한 단어만)
SAAS_BRANDABLE_WORDS = {
    # 강력한 음성/에너지
    "forge", "pulse", "nexus", "apex", "orbit", "nova", "beacon",
    "vault", "spark", "craft", "bolt", "arc", "ion", "flint", "rock",
    "stone", "steel", "iron", "gold", "silver", "carbon", "silicon",
    "neon", "helium", "lithium", "titanium", "platinum", "cobalt",
    "zinc", "copper", "brass", "bronze", "metal", "alloy", "tungsten",

    # 동력/에너지
    "surge", "flame", "blaze", "glow", "shine", "bright", "flash",
    "volt", "watt", "amp", "hertz", "cycle", "rhythm", "beat", "tempo",
    "pace", "speed", "velocity", "momentum", "force", "power", "drive",
    "boost", "lift", "rise", "jump", "spring", "bounce", "vault",

    # 추상/긍정적 이미지
    "flow", "core", "stack", "mesh", "grid", "sphere", "circle",
    "ring", "loop", "spiral", "vortex", "prism", "lens", "mirror",
    "sonic", "audio", "visual", "optic", "chroma", "spectrum", "pixel",
    "vector", "matrix", "tensor", "scalar", "quantum", "atom", "molecule",

    # 기술 브랜드 어원
    "apache", "nginx", "docker", "kubernetes", "linux", "ubuntu",
    "debian", "redhat", "canonical", "oracle", "mysql", "postgresql",
    "mongodb", "redis", "elasticsearch", "kafka", "rabbitmq",
}

# 통합 Whitelist
SAAS_WHITELIST = SAAS_FUNCTIONAL_WORDS | SAAS_BRANDABLE_WORDS


def is_whitelisted(word: str) -> bool:
    """
    단어가 SaaS whitelist에 포함되어 있는지 확인합니다.

    Args:
        word: 확인할 단어 (소문자로 가정)

    Returns:
        True이면 whitelist에 포함된 명백한 SaaS 단어
    """
    return word.lower() in SAAS_WHITELIST


def get_whitelist_category(word: str) -> str | None:
    """
    단어가 속한 whitelist 카테고리를 반환합니다.

    Returns:
        'functional', 'brandable', 또는 None
    """
    word_lower = word.lower()

    if word_lower in SAAS_FUNCTIONAL_WORDS:
        return "functional"
    elif word_lower in SAAS_BRANDABLE_WORDS:
        return "brandable"

    return None


# Whitelist 통계 (참고용)
WHITELIST_STATS = {
    "functional_count": len(SAAS_FUNCTIONAL_WORDS),
    "brandable_count": len(SAAS_BRANDABLE_WORDS),
    "total_count": len(SAAS_WHITELIST),
}
