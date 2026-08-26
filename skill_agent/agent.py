from google.adk.agents import Agent
from .tools import (
    save_skills,
    edit_skill,
    remove_skill,
    add_skill,
    approve_skills,
    list_approved_skills,
    save_problems,
    diagnose,
    create_class,
    list_classes,
    assign_to_class,
    find_topic
)

skill_agent = Agent(
    name="skill_agent",
    model="gemini-3.5-flash",
    description="Breaks a school topic into concrete, assessable skills.",
    instruction=(
        "Break the teacher's topic into distinct skills a student must master. "
        "Each skill must be concrete and individually assessable. Call "
        "save_skills, then report the skills, and ask the "
        "teacher to approve them."
        "The teacher may accept the skills, reword one, remove one, or add one. "
        "Use edit_skill, remove_skill or add_skill as asked, show the revised list, "
        "and ask again. Only call approve_skills when the teacher confirms the whole "
        "list is right."
    ),
    tools=[save_skills, approve_skills, edit_skill, remove_skill, add_skill, create_class, list_classes],
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
        "Write open-response problems that require the student to show their "
        "reasoning or working. Never multiple choice — the grader needs to see how "
        "the student got there, not just what they picked."
        "After the teacher approves the problems, ask which class this is for and "
        "when it's due, then call assign_to_class. If they haven't created a class "
        "yet, call create_class first."
    ),
    tools=[list_approved_skills, save_problems, assign_to_class],
)

diagnostic_agent = Agent(
    name="diagnostic_agent",
    model="gemini-3.5-flash",
    description="Tells the teacher what to reteach and what to leave alone.",
    instruction=(
        "Call diagnose for the topic_id. Report in this order, in plain "
        "language, under 200 words — the teacher is reading between lessons.\n"
        "1. Coverage first: how many of the expected submissions arrived. If any are "
        "missing, name those students separately from students who answered wrongly — "
        "not submitting is a different problem from not understanding.\n"
        "2. Skills needing a whole-class reteach. Do not name students; the "
        "whole class relearns it.\n"
        "3. Individual gaps, naming the students.\n"
        "4. Skills the class has mastered, so they can move on.\n"
        "5. If the same students appear in three or more individual gaps, say "
        "so explicitly — that is a signal about those students, not the skills.\n"
        "6. For any student with procedural slips, name the student, the skill, and "
        "what specifically went wrong — e.g. they understand the concept and need accuracy "
        "practice, not reteaching. Do the same for prerequisite gaps, naming which "
        "earlier skill is missing. Use the misconception text; do not summarise it "
        "into a count."
        "Use each skill's name exactly as diagnose returned it. Never invent "
        "numbers — use only what diagnose returned."
    ),
    tools=[diagnose],
)

root_agent = Agent(
    name="coordinator",
    model="gemini-3.5-flash",
    description="Coordinates lesson preparation for a teacher.",
    instruction=(
        "You coordinate lesson prep. Send topic breakdown and approval to "
        "skill_agent. Once skills are approved, hand off to problem_agent to "
        "generate leveled problems. When the teacher asks how the class did, "
        "or what to reteach, hand off to diagnostic_agent. Never skip the "
        "teacher's approval step."
        "Never ask the teacher for a topic_id or class_id — they are internal. Track "
        "the topic you are working on from earlier in the conversation. If the "
        "teacher refers to past work, call find_topic with words from their "
        "description. Refer to topics by title and classes by name."
    ),
    sub_agents=[skill_agent, problem_agent, diagnostic_agent],
    tools=[find_topic],
)
