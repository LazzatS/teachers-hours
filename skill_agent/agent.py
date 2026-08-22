from google.adk.agents import Agent

root_agent = Agent(
    name="skill_agent",
    model="gemini-3.5-flash",
    description="Breaks a school topic into teachable skills.",
    instruction=(
        "Given a school topic, list the distinct skills a student must "
        "master to understand it. Return a plain numbered list, nothing else."
    ),
)
