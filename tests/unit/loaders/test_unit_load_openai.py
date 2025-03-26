import os
import pytest
from unittest.mock import patch, MagicMock

from any_agent.schema import AgentSchema
from any_agent.loaders.openai import (
    load_openai_agent,
)
from any_agent.tools import (
    show_final_answer,
    ask_user_verification,
    search_web,
    visit_webpage,
)


def test_load_openai_agent_default():
    mock_agent = MagicMock()
    mock_function_tool = MagicMock()

    with (
        patch("any_agent.loaders.openai.Agent", mock_agent),
        patch("agents.function_tool", mock_function_tool),
    ):
        load_openai_agent(main_agent=AgentSchema(model_id="gpt-4o"))
        mock_agent.assert_called_once_with(
            name="default-name",
            model="gpt-4o",
            instructions=None,
            handoffs=[],
            tools=[mock_function_tool(search_web), mock_function_tool(visit_webpage)],
        )


def test_run_openai_agent_with_api_base_and_api_key_var():
    mock_agent = MagicMock()
    async_openai_mock = MagicMock()
    openai_chat_completions_model = MagicMock()
    with (
        patch("any_agent.loaders.openai.Agent", mock_agent),
        patch("any_agent.loaders.openai.AsyncOpenAI", async_openai_mock),
        patch(
            "any_agent.loaders.openai.OpenAIChatCompletionsModel",
            openai_chat_completions_model,
        ),
        patch.dict(os.environ, {"TEST_API_KEY": "test-key-12345"}),
    ):
        load_openai_agent(
            main_agent=AgentSchema(
                model_id="gpt-4o", api_base="FOO", api_key_var="TEST_API_KEY"
            ),
        )
        async_openai_mock.assert_called_once_with(
            api_key="test-key-12345",
            base_url="FOO",
        )
        openai_chat_completions_model.assert_called_once()


def test_run_openai_environment_error():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(KeyError, match="MISSING_KEY"):
            load_openai_agent(
                main_agent=AgentSchema(
                    model_id="gpt-4o", api_base="FOO", api_key_var="MISSING_KEY"
                ),
            )


def test_load_openai_multiagent():
    mock_agent = MagicMock()
    mock_function_tool = MagicMock()

    with (
        patch("any_agent.loaders.openai.Agent", mock_agent),
        patch("agents.function_tool", mock_function_tool),
    ):
        load_openai_agent(
            main_agent=AgentSchema(
                model_id="o3-mini",
            ),
            managed_agents=[
                AgentSchema(
                    model_id="gpt-4o-mini",
                    name="user-verification-agent",
                    tools=["any_agent.tools.ask_user_verification"],
                ),
                AgentSchema(
                    model_id="gpt-4o",
                    name="search-web-agent",
                    tools=[
                        "any_agent.tools.search_web",
                        "any_agent.tools.visit_webpage",
                    ],
                ),
                AgentSchema(
                    model_id="gpt-4o-mini",
                    name="communication-agent",
                    tools=["any_agent.tools.show_final_answer"],
                    handoff=True,
                ),
            ],
        )
        mock_agent.assert_any_call(
            model="gpt-4o-mini",
            instructions=None,
            name="user-verification-agent",
            tools=[
                mock_function_tool(ask_user_verification),
            ],
        )

        mock_agent.assert_any_call(
            model="gpt-4o",
            instructions=None,
            name="search-web-agent",
            tools=[mock_function_tool(search_web), mock_function_tool(visit_webpage)],
        )

        mock_agent.assert_any_call(
            model="gpt-4o-mini",
            instructions=None,
            name="communication-agent",
            tools=[mock_function_tool(show_final_answer)],
        )

        mock_agent.assert_any_call(
            model="o3-mini",
            instructions=None,
            name="default-name",
            handoffs=[mock_agent.return_value],
            tools=[
                mock_agent.return_value.as_tool.return_value,
                mock_agent.return_value.as_tool.return_value,
            ],
        )
