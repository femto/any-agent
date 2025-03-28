# any-agent

A single interface for different Agent frameworks

```py
from random import choice
from any_agent import AgentFramework, AgentConfig, AnyAgent

framework = AgentFramework(
    choice([AgentFramework.LANGCHAIN, AgentFramework.OPENAI, AgentFramework.SMOLAGENTS]))

agent_config = AgentConfig(model_id="gpt-4o-mini")

agent = AnyAgent.create(framework, agent_config)

agent.run("What day is today?")
```
