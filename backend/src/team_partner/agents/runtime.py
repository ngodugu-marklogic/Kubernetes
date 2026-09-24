import uuid
from collections.abc import Iterable

from hyperforge.harness_sdk import AgentHarness, HarnessTool, ModelClient, NucliaModelClient
from sqlalchemy.orm import Session, sessionmaker

from team_partner.agents.storage import SQLiteHarnessStorage
from team_partner.settings import EnvSettings

SYSTEM_PROMPT = (
    "You are an AI team partner and scrum master. Help the team plan, collaborate, "
    "identify blockers, and make progress. Ground claims about Jira, GitHub, and team "
    "activity in tool results; never claim you reviewed a source you cannot access. "
    "Read get_team_context before deciding which team members, Jira boards, or GitHub "
    "repositories to investigate. Use the saved scope to focus analysis; ask for missing "
    "context when needed. When the user provides or changes team scope, save it with the "
    "appropriate tool. Summarize actionable next steps."
)


async def open_agent(
    *,
    factory: sessionmaker[Session],
    settings: EnvSettings,
    conversation_id: str,
    model_client: ModelClient | None = None,
    tools: Iterable[HarnessTool] = (),
) -> tuple[AgentHarness, bool]:
    storage = SQLiteHarnessStorage(factory)
    existing = await storage.get_conversation(conversation_id)
    if existing is None:
        raise ValueError("Conversation not found")
    if model_client is None:
        if not settings.nua_api_key:
            raise RuntimeError("NUA_API_KEY is required for agent conversations")
        model_client = await NucliaModelClient.from_api_key(settings.nua_api_key, base_url=settings.nua_api_uri)
        owns_client = True
    else:
        owns_client = False
    agent = AgentHarness(
        model=settings.default_chat_model,
        model_client=model_client,
        tools=tools,
        storage=storage,
        conversation_id=conversation_id,
        system_prompt=SYSTEM_PROMPT,
        category="assistant",
    )
    agent.agent_id = str(existing.metadata.get("root_agent_id", uuid.uuid4().hex))
    try:
        await agent.load(create=False)
    except BaseException:
        if owns_client:
            await model_client.aclose()
        raise
    return agent, owns_client
