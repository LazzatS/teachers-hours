from google.adk.agents import Agent
from .tools import (
    save_skills,
    edit_skill,
    remove_skill,
    add_skill,
    approve_skills,
    list_approved_skills,
    save_problems
)

skill_agent = Agent(
    name="skill_agent",
    model="gemini-3.5-flash",
    description="Breaks a school topic into concrete, assessable skills.",
    instruction=(
        "Break the teacher's topic into distinct skills a student must master. "
        "Each skill must be concrete and individually assessable. Call "
        "save_skills, then report the topic_id and the skills, and ask the "
        "teacher to approve them."
        "The teacher may accept the skills, reword one, remove one, or add one. "
        "Use edit_skill, remove_skill or add_skill as asked, show the revised list, "
        "and ask again. Only call approve_skills when the teacher confirms the whole "
        "list is right."
    ),
    tools=[save_skills, approve_skills, edit_skill, remove_skill, add_skill],
)

problem_agent = Agent(
    name="problem_agent",
    model="gemini-3.5-flash",
    description="Writes leveled practice problems for approved skills.",
    instruction=(
        "Call list_approved_skills for the topic_id. For each approved skill, "
        "write three problems — low, medium and hard — that test only that "
        "skill, and call save_problems once per skill. Never generate problems "
        "for skills that are not approved."
    ),
    tools=[list_approved_skills, save_problems],
)

root_agent = Agent(
    name="coordinator",
    model="gemini-3.5-flash",
    description="Coordinates lesson preparation for a teacher.",
    instruction=(
        "You coordinate lesson prep. Send topic breakdown and approval to "
        "skill_agent. Once skills are approved, hand off to problem_agent to "
        "generate leveled problems. Never skip the teacher's approval step."
    ),
    sub_agents=[skill_agent, problem_agent],
)
