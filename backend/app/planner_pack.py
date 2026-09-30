"""Planner pack — 60 real-world Goal → Objectives → Projects → Tasks examples.

Two jobs:
1. retrieve(goal): nearest 2 examples by word overlap, injected into the compile
   prompt so decomposition quality improves without retraining any model.
2. Eval battery: every example asserts the planner's shape rules, so quality is
   a measured number that cannot regress. Decomposition compounds.

Kinds: r=research c=create b=browse a=approval h=human w=wait.
Sensitive rule (from the spec): passwords/credentials stay behind the vault
(#53), money moves only with approval (#46, #55).
"""
import re

r, c, b, a, h, w = "research", "create", "browse", "approval", "human", "wait"

EXAMPLES = [
{"goal": "Prepare my company for a fundraising meeting.",
 "objectives": [
  {"title": "Research investors", "projects": [
   {"title": "Investor Research", "tasks": [
    ("Search investors", b), ("Collect investor information", r), ("Create investor shortlist", c),
    ("Research investment thesis", r)]}]},
  {"title": "Prepare company information", "projects": [
   {"title": "Financial Preparation", "tasks": [
    ("Prepare financial summary", c)]}]},
  {"title": "Create pitch material", "projects": [
   {"title": "Pitch Preparation", "tasks": [
    ("Draft pitch deck", c), ("Draft investor emails", c), ("Send emails", a)]}]},
  {"title": "Schedule meetings", "projects": [
   {"title": "Meeting Scheduling", "tasks": [("Schedule meetings", c)]}]}]},
{"goal": "Launch my new startup.",
 "objectives": [
  {"title": "Validate the idea", "projects": [
   {"title": "Market Validation", "tasks": [
    ("Research competitors", r), ("Interview potential customers", h), ("Define target audience", r)]}]},
  {"title": "Build MVP", "projects": [
   {"title": "MVP Development", "tasks": [
    ("Define MVP features", c), ("Create development plan", c), ("Build landing page", c),
    ("Configure domain", c), ("Create product demo", c)]}]},
  {"title": "Prepare marketing", "projects": [
   {"title": "Marketing", "tasks": [("Prepare launch announcement", c)]}]},
  {"title": "Launch publicly", "projects": [
   {"title": "Launch", "tasks": [("Publish product", a)]}]}]},
{"goal": "Find 100 potential customers for my SaaS product.",
 "objectives": [
  {"title": "Define ideal customer", "projects": [
   {"title": "ICP Definition", "tasks": [("Define industry", r), ("Define company size", r)]}]},
  {"title": "Find companies", "projects": [
   {"title": "Lead Research", "tasks": [
    ("Search companies", b), ("Filter companies", r), ("Add leads to CRM", c), ("Segment leads", c)]}]},
  {"title": "Identify decision makers", "projects": [
   {"title": "Contact Discovery", "tasks": [
    ("Find decision makers", r), ("Find contact information", r), ("Verify contacts", r)]}]},
  {"title": "Create outreach list", "projects": [
   {"title": "Outreach Preparation", "tasks": [("Prepare outreach messages", c)]}]}]},
{"goal": "Plan my three-day business trip to Mumbai.",
 "objectives": [
  {"title": "Arrange transportation", "projects": [
   {"title": "Transportation", "tasks": [
    ("Search flights", b), ("Compare flight times", r), ("Book flight", a)]}]},
  {"title": "Book accommodation", "projects": [
   {"title": "Hotel", "tasks": [("Search hotels", b), ("Compare hotels", r), ("Book hotel", a)]}]},
  {"title": "Schedule meetings", "projects": [
   {"title": "Meetings", "tasks": [("Contact meeting participants", h), ("Schedule meetings", c)]}]},
  {"title": "Create itinerary", "projects": [
   {"title": "Itinerary", "tasks": [("Create daily itinerary", c), ("Add bookings to calendar", c)]}]}]},
{"goal": "Organize our company's annual conference.",
 "objectives": [
  {"title": "Select venue", "projects": [
   {"title": "Venue", "tasks": [("Research venues", r), ("Request quotations", h), ("Compare venue options", r)]}]},
  {"title": "Invite speakers", "projects": [
   {"title": "Speakers", "tasks": [("Contact speakers", h), ("Confirm speakers", h)]}]},
  {"title": "Manage attendees", "projects": [
   {"title": "Attendees", "tasks": [
    ("Create registration form", c), ("Send invitations", a), ("Track registrations", r)]}]},
  {"title": "Prepare event logistics", "projects": [
   {"title": "Logistics", "tasks": [("Arrange catering", h), ("Prepare event schedule", c)]}]}]},
{"goal": "Hire a senior software engineer.",
 "objectives": [
  {"title": "Define requirements", "projects": [
   {"title": "Job Definition", "tasks": [("Write job description", c), ("Define required skills", c)]}]},
  {"title": "Find candidates", "projects": [
   {"title": "Candidate Search", "tasks": [
    ("Publish job", a), ("Search candidates", b), ("Shortlist candidates", r), ("Contact candidates", h)]}]},
  {"title": "Evaluate candidates", "projects": [
   {"title": "Interviews", "tasks": [
    ("Schedule interviews", c), ("Collect interview feedback", h), ("Check references", h)]}]},
  {"title": "Complete hiring", "projects": [
   {"title": "Hiring", "tasks": [("Prepare offer", a)]}]}]},
{"goal": "Improve our company website to generate more leads.",
 "objectives": [
  {"title": "Audit current website", "projects": [
   {"title": "Website Audit", "tasks": [
    ("Crawl website", b), ("Identify broken links", r), ("Analyze landing pages", r)]}]},
  {"title": "Improve content", "projects": [
   {"title": "Content", "tasks": [
    ("Review copy", r), ("Identify missing information", r), ("Rewrite homepage", c), ("Add testimonials", c)]}]},
  {"title": "Improve conversion", "projects": [
   {"title": "Conversion Optimization", "tasks": [("Improve CTA", c)]}]},
  {"title": "Measure results", "projects": [
   {"title": "Analytics", "tasks": [("Configure analytics", c), ("Monitor conversions", r)]}]}]},
{"goal": "Prepare our product for launch next month.",
 "objectives": [
  {"title": "Finalize product", "projects": [
   {"title": "Product Readiness", "tasks": [
    ("Review remaining bugs", r), ("Test critical workflows", r), ("Prepare documentation", c)]}]},
  {"title": "Prepare marketing", "projects": [
   {"title": "Marketing", "tasks": [
    ("Create launch page", c), ("Create announcement", c), ("Prepare social posts", c)]}]},
  {"title": "Prepare customers", "projects": [
   {"title": "Customer Communication", "tasks": [("Email existing customers", a), ("Prepare demo", c)]}]},
  {"title": "Launch product", "projects": [
   {"title": "Launch", "tasks": [("Schedule launch", c), ("Monitor launch", r)]}]}]},
{"goal": "Understand our top competitors.",
 "objectives": [
  {"title": "Identify competitors", "projects": [
   {"title": "Competitor Discovery", "tasks": [("Search competitors", b), ("Visit competitor websites", b)]}]},
  {"title": "Analyze products", "projects": [
   {"title": "Product Analysis", "tasks": [
    ("Collect product information", r), ("Analyze features", r), ("Read customer reviews", r)]}]},
  {"title": "Compare pricing", "projects": [
   {"title": "Pricing Analysis", "tasks": [("Collect pricing", r)]}]},
  {"title": "Identify market positioning", "projects": [
   {"title": "Positioning", "tasks": [
    ("Identify strengths", r), ("Identify weaknesses", r), ("Create comparison", c), ("Prepare summary", c)]}]}]},
{"goal": "Create a marketing campaign for our new product.",
 "objectives": [
  {"title": "Define audience", "projects": [
   {"title": "Audience Research", "tasks": [
    ("Define target audience", r), ("Research customer pain points", r), ("Create positioning", c)]}]},
  {"title": "Create messaging", "projects": [
   {"title": "Messaging", "tasks": [("Write campaign message", c)]}]},
  {"title": "Create content", "projects": [
   {"title": "Content", "tasks": [
    ("Create landing page", c), ("Create social posts", c), ("Create email campaign", c),
    ("Prepare advertisements", c)]}]},
  {"title": "Launch campaign", "projects": [
   {"title": "Campaign Launch", "tasks": [("Schedule campaign", a), ("Track results", r)]}]}]},
{"goal": "Organize my personal finances.",
 "objectives": [
  {"title": "Understand spending", "projects": [
   {"title": "Expense Analysis", "tasks": [
    ("Collect transaction information", r), ("Categorize expenses", r), ("Identify recurring payments", r),
    ("Identify unnecessary subscriptions", r), ("Calculate monthly spending", r)]}]},
  {"title": "Organize accounts", "projects": [
   {"title": "Account Organization", "tasks": [("Create financial dashboard", c)]}]},
  {"title": "Create budget", "projects": [
   {"title": "Budget", "tasks": [("Create budget", c), ("Review monthly expenses", r)]}]},
  {"title": "Set financial goals", "projects": [
   {"title": "Goals", "tasks": [("Set savings target", c)]}]}]},
{"goal": "Plan a one-week vacation to Japan.",
 "objectives": [
  {"title": "Research destinations", "projects": [
   {"title": "Destination Research", "tasks": [("Research cities", r), ("Compare travel routes", r)]}]},
  {"title": "Plan transportation", "projects": [
   {"title": "Flights", "tasks": [("Search flights", b), ("Compare flights", r)]}]},
  {"title": "Book accommodation", "projects": [
   {"title": "Hotels", "tasks": [("Search hotels", b), ("Book hotel", a)]}]},
  {"title": "Create itinerary", "projects": [
   {"title": "Activities", "tasks": [
    ("Research attractions", r), ("Find restaurants", r), ("Create itinerary", c),
    ("Add bookings to calendar", c)]}]}]},
{"goal": "Prepare a presentation for tomorrow's client meeting.",
 "objectives": [
  {"title": "Understand client", "projects": [
   {"title": "Client Research", "tasks": [
    ("Review client information", r), ("Identify meeting objectives", r)]}]},
  {"title": "Prepare content", "projects": [
   {"title": "Content", "tasks": [
    ("Collect relevant data", r), ("Create presentation outline", c), ("Prepare talking points", c)]}]},
  {"title": "Create presentation", "projects": [
   {"title": "Slides", "tasks": [("Create slides", c), ("Add charts", c), ("Review presentation", r)]}]},
  {"title": "Rehearse", "projects": [
   {"title": "Rehearsal", "tasks": [("Rehearse presentation", h)]}]}]},
{"goal": "Determine whether we should enter the European SaaS market.",
 "objectives": [
  {"title": "Understand market", "projects": [
   {"title": "Market Research", "tasks": [
    ("Research market size", r), ("Identify regulations", r), ("Research distribution channels", r)]}]},
  {"title": "Analyze competitors", "projects": [
   {"title": "Competitor Research", "tasks": [("Identify competitors", b), ("Analyze pricing", r)]}]},
  {"title": "Understand customers", "projects": [
   {"title": "Customer Research", "tasks": [("Research customer segments", r)]}]},
  {"title": "Evaluate opportunity", "projects": [
   {"title": "Opportunity Analysis", "tasks": [
    ("Identify barriers", r), ("Estimate costs", r), ("Prepare market analysis", c)]}]}]},
{"goal": "Build a sales pipeline for our enterprise product.",
 "objectives": [
  {"title": "Define target accounts", "projects": [
   {"title": "Account Research", "tasks": [("Define ICP", r), ("Search target companies", b)]}]},
  {"title": "Find prospects", "projects": [
   {"title": "Lead Generation", "tasks": [
    ("Identify decision makers", r), ("Research companies", r), ("Add prospects to CRM", c)]}]},
  {"title": "Qualify leads", "projects": [
   {"title": "Qualification", "tasks": [
    ("Score according to predefined criteria", r), ("Segment leads", c)]}]},
  {"title": "Begin outreach", "projects": [
   {"title": "Outreach", "tasks": [("Draft outreach", c), ("Send outreach", a), ("Schedule calls", c)]}]}]},
{"goal": "Find a new apartment in Bangalore.",
 "objectives": [
  {"title": "Define requirements", "projects": [
   {"title": "Requirements", "tasks": [("Define budget", r), ("Define preferred locations", r)]}]},
  {"title": "Search properties", "projects": [
   {"title": "Property Search", "tasks": [("Search listings", b), ("Filter properties", r)]}]},
  {"title": "Compare options", "projects": [
   {"title": "Comparison", "tasks": [
    ("Compare prices", r), ("Check amenities", r), ("Record shortlisted properties", c)]}]},
  {"title": "Arrange visits", "projects": [
   {"title": "Visits", "tasks": [("Contact landlords", h), ("Schedule visits", c)]}]}]},
{"goal": "Organize my wedding.",
 "objectives": [
  {"title": "Select venue", "projects": [
   {"title": "Venue", "tasks": [("Research venues", r), ("Request quotations", h), ("Compare venues", r)]}]},
  {"title": "Arrange vendors", "projects": [
   {"title": "Vendors", "tasks": [("Find caterers", r), ("Find photographers", r), ("Find decorators", r)]}]},
  {"title": "Manage guests", "projects": [
   {"title": "Guests", "tasks": [("Create guest list", c), ("Send invitations", a), ("Track RSVPs", r)]}]},
  {"title": "Coordinate event", "projects": [
   {"title": "Event Planning", "tasks": [("Create event schedule", c)]}]}]},
{"goal": "Learn Python well enough to build small applications.",
 "objectives": [
  {"title": "Learn fundamentals", "projects": [
   {"title": "Python Fundamentals", "tasks": [
    ("Learn variables", r), ("Learn functions", r), ("Learn classes", r)]}]},
  {"title": "Practice programming", "projects": [
   {"title": "Practice", "tasks": [("Practice loops", r), ("Practice data structures", r)]}]},
  {"title": "Build projects", "projects": [
   {"title": "Projects", "tasks": [
    ("Build calculator", c), ("Build API client", c), ("Build small web application", c)]}]},
  {"title": "Evaluate progress", "projects": [
   {"title": "Assessment", "tasks": [("Review mistakes", r), ("Complete final project", a)]}]}]},
{"goal": "Prepare me for a software engineering interview.",
 "objectives": [
  {"title": "Understand requirements", "projects": [
   {"title": "Topic Preparation", "tasks": [
    ("Review job description", r), ("Identify required skills", r)]}]},
  {"title": "Study technical topics", "projects": [
   {"title": "Coding Practice", "tasks": [
    ("Study algorithms", r), ("Solve coding problems", r), ("Study system design", r)]}]},
  {"title": "Practice problems", "projects": [
   {"title": "System Design", "tasks": [("Prepare behavioral answers", c)]}]},
  {"title": "Practice interviews", "projects": [
   {"title": "Mock Interviews", "tasks": [
    ("Conduct mock interview", h), ("Review mistakes", r), ("Repeat weak areas", r)]}]}]},
{"goal": "Create a research report about AI agents.",
 "objectives": [
  {"title": "Define research questions", "projects": [
   {"title": "Research", "tasks": [("Define questions", r)]}]},
  {"title": "Collect information", "projects": [
   {"title": "Data Collection", "tasks": [
    ("Search academic sources", b), ("Search company information", b), ("Collect evidence", r),
    ("Organize sources", c)]}]},
  {"title": "Analyze findings", "projects": [
   {"title": "Analysis", "tasks": [("Compare approaches", r), ("Identify trends", r)]}]},
  {"title": "Write report", "projects": [
   {"title": "Report", "tasks": [("Draft report", c), ("Review citations", r), ("Finalize report", a)]}]}]},
{"goal": "Launch an online store for my clothing business.",
 "objectives": [
  {"title": "Set up store", "projects": [
   {"title": "Store Setup", "tasks": [
    ("Select ecommerce platform", r), ("Configure store", c), ("Add domain", c)]}]},
  {"title": "Add products", "projects": [
   {"title": "Product Catalog", "tasks": [
    ("Add products", c), ("Upload product images", c), ("Add descriptions", c)]}]},
  {"title": "Configure payments", "projects": [
   {"title": "Payments", "tasks": [("Configure payment gateway", a), ("Configure shipping", c)]}]},
  {"title": "Launch marketing", "projects": [
   {"title": "Marketing", "tasks": [("Test checkout", r), ("Launch store", a)]}]}]},
{"goal": "Reduce the time our team spends answering repetitive customer questions.",
 "objectives": [
  {"title": "Identify repetitive questions", "projects": [
   {"title": "Support Analysis", "tasks": [
    ("Analyze support tickets", r), ("Categorize questions", r), ("Identify repetitive questions", r)]}]},
  {"title": "Create knowledge base", "projects": [
   {"title": "Knowledge Base", "tasks": [("Write answers", c), ("Create FAQ", c)]}]},
  {"title": "Automate common responses", "projects": [
   {"title": "Automation", "tasks": [("Configure chatbot", c), ("Create escalation rules", c)]}]},
  {"title": "Measure improvement", "projects": [
   {"title": "Measurement", "tasks": [("Monitor support volume", r), ("Review unresolved questions", r)]}]}]},
{"goal": "Organize all our company documents.",
 "objectives": [
  {"title": "Find documents", "projects": [
   {"title": "Document Discovery", "tasks": [("Search folders", b), ("Identify document types", r)]}]},
  {"title": "Categorize documents", "projects": [
   {"title": "Categorization", "tasks": [("Identify duplicates", r)]}]},
  {"title": "Remove duplicates", "projects": [
   {"title": "Cleanup", "tasks": [
    ("Rename files", c), ("Move documents", c), ("Archive outdated documents", a)]}]},
  {"title": "Create structure", "projects": [
   {"title": "Organization", "tasks": [("Create folder structure", c), ("Create naming conventions", c)]}]}]},
{"goal": "Prepare our monthly business review.",
 "objectives": [
  {"title": "Collect business metrics", "projects": [
   {"title": "Data Collection", "tasks": [
    ("Collect revenue", r), ("Collect customer metrics", r), ("Collect sales data", r)]}]},
  {"title": "Analyze performance", "projects": [
   {"title": "Analysis", "tasks": [("Compare targets", r), ("Identify deviations", r), ("Analyze causes", r)]}]},
  {"title": "Identify problems", "projects": [
   {"title": "Problem Review", "tasks": [("Prepare charts", c)]}]},
  {"title": "Prepare presentation", "projects": [
   {"title": "Presentation", "tasks": [("Create presentation", c), ("Schedule review meeting", c)]}]}]},
{"goal": "Build a five-person sales team.",
 "objectives": [
  {"title": "Define roles", "projects": [
   {"title": "Hiring Plan", "tasks": [("Define sales roles", c), ("Write job descriptions", c)]}]},
  {"title": "Find candidates", "projects": [
   {"title": "Recruitment", "tasks": [("Publish jobs", a), ("Search candidates", b), ("Shortlist candidates", r)]}]},
  {"title": "Interview candidates", "projects": [
   {"title": "Interviews", "tasks": [
    ("Schedule interviews", c), ("Conduct interviews", h), ("Send offers", a)]}]},
  {"title": "Hire team", "projects": [
   {"title": "Onboarding", "tasks": [("Prepare onboarding materials", c)]}]}]},
{"goal": "Create a system that helps me manage my daily work.",
 "objectives": [
  {"title": "Capture tasks", "projects": [
   {"title": "Task Management", "tasks": [("Collect outstanding tasks", r), ("Categorize tasks", r)]}]},
  {"title": "Organize priorities", "projects": [
   {"title": "Prioritization", "tasks": [("Identify deadlines", r), ("Define priorities", c)]}]},
  {"title": "Schedule work", "projects": [
   {"title": "Scheduling", "tasks": [
    ("Create daily schedule", c), ("Add tasks to calendar", c), ("Create reminders", c)]}]},
  {"title": "Review progress", "projects": [
   {"title": "Review", "tasks": [("Review completed tasks", r), ("Reschedule unfinished work", c)]}]}]},
{"goal": "Prepare everything needed for our board meeting.",
 "objectives": [
  {"title": "Collect company metrics", "projects": [
   {"title": "Metrics", "tasks": [("Collect revenue metrics", r), ("Collect growth metrics", r)]}]},
  {"title": "Prepare financial information", "projects": [
   {"title": "Finance", "tasks": [("Prepare financial summary", c), ("Review major projects", r)]}]},
  {"title": "Prepare strategic updates", "projects": [
   {"title": "Strategy", "tasks": [("Prepare strategic updates", c), ("Identify risks", r)]}]},
  {"title": "Create board materials", "projects": [
   {"title": "Board Deck", "tasks": [
    ("Create board deck", c), ("Review presentation", r), ("Send materials to participants", a)]}]}]},
{"goal": "Launch a technology podcast.",
 "objectives": [
  {"title": "Define podcast concept", "projects": [
   {"title": "Podcast Concept", "tasks": [
    ("Define audience", r), ("Choose podcast name", c), ("Create branding", c)]}]},
  {"title": "Prepare production", "projects": [
   {"title": "Production", "tasks": [("Select recording software", r)]}]},
  {"title": "Find guests", "projects": [
   {"title": "Guest Management", "tasks": [
    ("Create guest list", c), ("Contact guests", h), ("Schedule recordings", c)]}]},
  {"title": "Publish episodes", "projects": [
   {"title": "Publishing", "tasks": [("Record episode", c), ("Edit episode", c), ("Publish episode", a)]}]}]},
{"goal": "Build a YouTube channel about AI.",
 "objectives": [
  {"title": "Define content strategy", "projects": [
   {"title": "Strategy", "tasks": [("Define audience", r), ("Research topics", r)]}]},
  {"title": "Create channel", "projects": [
   {"title": "Channel Setup", "tasks": [("Create channel", c), ("Design banner", c)]}]},
  {"title": "Produce videos", "projects": [
   {"title": "Production", "tasks": [
    ("Write video scripts", c), ("Record videos", c), ("Edit videos", c), ("Create thumbnails", c)]}]},
  {"title": "Publish consistently", "projects": [
   {"title": "Publishing", "tasks": [("Upload videos", a), ("Analyze performance", r)]}]}]},
{"goal": "Automate our invoice processing.",
 "objectives": [
  {"title": "Understand current process", "projects": [
   {"title": "Process Analysis", "tasks": [("Document current workflow", r), ("Identify manual steps", r)]}]},
  {"title": "Identify automation opportunities", "projects": [
   {"title": "Automation Design", "tasks": [("Identify data sources", r), ("Define automation rules", c)]}]},
  {"title": "Build workflow", "projects": [
   {"title": "Implementation", "tasks": [("Build workflow", c), ("Connect accounting system", a)]}]},
  {"title": "Test automation", "projects": [
   {"title": "Testing", "tasks": [("Test invoices", r), ("Handle exceptions", h), ("Monitor workflow", r)]}]}]},
{"goal": "Prepare my documents for tax filing.",
 "objectives": [
  {"title": "Collect documents", "projects": [
   {"title": "Document Collection", "tasks": [
    ("Collect statements", r), ("Collect income documents", r), ("Collect expense records", r)]}]},
  {"title": "Categorize income", "projects": [
   {"title": "Income", "tasks": [("Categorize transactions", r), ("Identify missing documents", r)]}]},
  {"title": "Categorize expenses", "projects": [
   {"title": "Expenses", "tasks": [("Organize files", c), ("Prepare summary", c)]}]},
  {"title": "Prepare information for filing", "projects": [
   {"title": "Filing Preparation", "tasks": [("Flag questions for accountant", h)]}]}]},
{"goal": "Create the product roadmap for the next six months.",
 "objectives": [
  {"title": "Understand customer needs", "projects": [
   {"title": "Customer Research", "tasks": [("Review customer feedback", r), ("Analyze feature requests", r)]}]},
  {"title": "Review existing product", "projects": [
   {"title": "Product Analysis", "tasks": [("Identify product problems", r), ("Review technical debt", r)]}]},
  {"title": "Prioritize initiatives", "projects": [
   {"title": "Prioritization", "tasks": [
    ("Define initiatives", c), ("Estimate effort", r), ("Define dependencies", r)]}]},
  {"title": "Create roadmap", "projects": [
   {"title": "Roadmap", "tasks": [("Create roadmap", c), ("Share roadmap", a)]}]}]},
{"goal": "Create a proposal for a large enterprise customer.",
 "objectives": [
  {"title": "Understand customer requirements", "projects": [
   {"title": "Customer Research", "tasks": [("Review customer requirements", r), ("Identify pain points", r)]}]},
  {"title": "Define solution", "projects": [
   {"title": "Solution Design", "tasks": [("Map requirements to product", r), ("Define implementation plan", c)]}]},
  {"title": "Prepare pricing", "projects": [
   {"title": "Pricing", "tasks": [("Calculate pricing", r)]}]},
  {"title": "Create proposal", "projects": [
   {"title": "Proposal", "tasks": [("Draft proposal", c), ("Review proposal", r), ("Send proposal", a)]}]}]},
{"goal": "Determine whether we should use a new database technology.",
 "objectives": [
  {"title": "Understand technology", "projects": [
   {"title": "Technology Research", "tasks": [
    ("Read documentation", r), ("Research architecture", r), ("Identify limitations", r)]}]},
  {"title": "Evaluate requirements", "projects": [
   {"title": "Requirements Analysis", "tasks": [("Define evaluation criteria", c)]}]},
  {"title": "Compare alternatives", "projects": [
   {"title": "Comparison", "tasks": [("Compare alternatives", r)]}]},
  {"title": "Test technology", "projects": [
   {"title": "Prototype", "tasks": [
    ("Build prototype", c), ("Run tests", r), ("Document findings", c),
    ("Make implementation recommendation based on predefined criteria", a)]}]}]},
{"goal": "Successfully onboard our new enterprise customer.",
 "objectives": [
  {"title": "Collect customer information", "projects": [
   {"title": "Customer Setup", "tasks": [("Collect requirements", h), ("Create account", c)]}]},
  {"title": "Configure account", "projects": [
   {"title": "Configuration", "tasks": [
    ("Configure settings", c), ("Import data", c), ("Configure integrations", a)]}]},
  {"title": "Train customer", "projects": [
   {"title": "Training", "tasks": [("Schedule training", c), ("Conduct training", h)]}]},
  {"title": "Confirm successful activation", "projects": [
   {"title": "Activation", "tasks": [("Test workflows", r), ("Confirm activation", a)]}]}]},
{"goal": "Organize a company offsite for our team.",
 "objectives": [
  {"title": "Select destination", "projects": [
   {"title": "Destination", "tasks": [
    ("Collect employee availability", h), ("Define budget", r), ("Research destinations", r)]}]},
  {"title": "Arrange travel", "projects": [
   {"title": "Travel", "tasks": [("Compare hotels", r), ("Arrange transportation", h)]}]},
  {"title": "Book accommodation", "projects": [
   {"title": "Accommodation", "tasks": [("Book accommodation", a)]}]},
  {"title": "Plan activities", "projects": [
   {"title": "Activities", "tasks": [
    ("Plan activities", c), ("Create itinerary", c), ("Send details to employees", a)]}]}]},
{"goal": "Improve our company's organic discovery.",
 "objectives": [
  {"title": "Audit current presence", "projects": [
   {"title": "SEO Audit", "tasks": [("Crawl website", b), ("Identify technical issues", r)]}]},
  {"title": "Research keywords/topics", "projects": [
   {"title": "Research", "tasks": [("Research search topics", r), ("Analyze competitors", r)]}]},
  {"title": "Improve website", "projects": [
   {"title": "Website Optimization", "tasks": [("Optimize pages", c), ("Add internal links", c)]}]},
  {"title": "Create content", "projects": [
   {"title": "Content", "tasks": [("Create content plan", c), ("Write articles", c), ("Monitor rankings", r)]}]}]},
{"goal": "Make our company easier for AI agents to discover and understand.",
 "objectives": [
  {"title": "Analyze current AI visibility", "projects": [
   {"title": "AI Visibility Audit", "tasks": [
    ("Identify important company facts", r), ("Audit public information", r),
    ("Test AI discovery queries", b), ("Monitor changes", r)]}]},
  {"title": "Improve company information", "projects": [
   {"title": "Information Architecture", "tasks": [("Review structured data", r)]}]},
  {"title": "Improve machine-readable content", "projects": [
   {"title": "Content", "tasks": [
    ("Improve product descriptions", c), ("Create authoritative documentation", c),
    ("Improve business profiles", c)]}]},
  {"title": "Monitor AI discovery", "projects": [
   {"title": "Monitoring", "tasks": [("Monitor changes", r)]}]}]},
{"goal": "Resolve the critical checkout bug.",
 "objectives": [
  {"title": "Reproduce problem", "projects": [
   {"title": "Investigation", "tasks": [
    ("Reproduce bug", r), ("Collect logs", r), ("Identify affected workflow", r),
    ("Identify root cause", r)]}]},
  {"title": "Identify cause", "projects": [
   {"title": "Fix", "tasks": [("Create fix", c)]}]},
  {"title": "Implement fix", "projects": [
   {"title": "Testing", "tasks": [("Run tests", r), ("Test checkout", r)]}]},
  {"title": "Verify solution", "projects": [
   {"title": "Deployment", "tasks": [("Deploy fix", a), ("Monitor errors", r)]}]}]},
{"goal": "Prepare for an important customer renewal.",
 "objectives": [
  {"title": "Understand customer usage", "projects": [
   {"title": "Account Analysis", "tasks": [("Review usage", r), ("Review support history", r)]}]},
  {"title": "Review account performance", "projects": [
   {"title": "Renewal Proposal", "tasks": [
    ("Review contract", r), ("Identify customer outcomes", r), ("Prepare renewal proposal", c)]}]},
  {"title": "Prepare renewal proposal", "projects": [
   {"title": "Customer Meeting", "tasks": [
    ("Draft email", c), ("Schedule meeting", c), ("Prepare talking points", c)]}]}]},
{"goal": "Migrate our application to a new cloud environment.",
 "objectives": [
  {"title": "Audit infrastructure", "projects": [
   {"title": "Infrastructure Audit", "tasks": [
    ("Inventory services", r), ("Document dependencies", r), ("Identify databases", r)]}]},
  {"title": "Design migration", "projects": [
   {"title": "Migration Design", "tasks": [("Create migration plan", c)]}]},
  {"title": "Migrate services", "projects": [
   {"title": "Migration", "tasks": [
    ("Configure environment", c), ("Migrate database", a), ("Deploy application", a)]}]},
  {"title": "Verify production", "projects": [
   {"title": "Verification", "tasks": [("Test services", r), ("Switch traffic", a), ("Monitor system", r)]}]}]},
{"goal": "Apply for this job.",
 "objectives": [
  {"title": "Understand job requirements", "projects": [
   {"title": "Job Analysis", "tasks": [("Read job description", r), ("Extract requirements", r)]}]},
  {"title": "Prepare application", "projects": [
   {"title": "Resume", "tasks": [
    ("Compare with resume", r), ("Customize resume", c), ("Draft cover letter", c)]}]},
  {"title": "Customize resume", "projects": [
   {"title": "Application", "tasks": [
    ("Review application", r), ("Fill application form", h), ("Submit application", a)]}]}]},
{"goal": "Clean up my email inbox.",
 "objectives": [
  {"title": "Identify important emails", "projects": [
   {"title": "Email Analysis", "tasks": [("Find unread emails", b), ("Identify urgent emails", r)]}]},
  {"title": "Remove unnecessary emails", "projects": [
   {"title": "Cleanup", "tasks": [("Identify newsletters", r), ("Archive unnecessary emails", a)]}]},
  {"title": "Organize remaining emails", "projects": [
   {"title": "Organization", "tasks": [("Create labels", c), ("Identify unanswered emails", r)]}]},
  {"title": "Respond to pending items", "projects": [
   {"title": "Responses", "tasks": [("Draft responses", c), ("Send approved responses", a)]}]}]},
{"goal": "Get our website redesign completed.",
 "objectives": [
  {"title": "Define scope", "projects": [
   {"title": "Planning", "tasks": [("Define requirements", c), ("Create project plan", c), ("Assign tasks", h)]}]},
  {"title": "Assign work", "projects": [
   {"title": "Design", "tasks": [("Review designs", r), ("Approve designs", a)]}]},
  {"title": "Track progress", "projects": [
   {"title": "Development", "tasks": [("Track development", r), ("Test website", r), ("Fix issues", c)]}]},
  {"title": "Launch redesign", "projects": [
   {"title": "Launch", "tasks": [("Deploy redesign", a)]}]}]},
{"goal": "Prepare a demo for a potential enterprise customer.",
 "objectives": [
  {"title": "Understand customer", "projects": [
   {"title": "Customer Research", "tasks": [("Research customer", r), ("Identify use cases", r)]}]},
  {"title": "Customize demo", "projects": [
   {"title": "Demo Customization", "tasks": [
    ("Prepare relevant data", r), ("Create demo flow", c), ("Prepare presentation", c)]}]},
  {"title": "Prepare environment", "projects": [
   {"title": "Environment", "tasks": [("Configure demo environment", c), ("Test demo", r)]}]},
  {"title": "Rehearse presentation", "projects": [
   {"title": "Rehearsal", "tasks": [("Rehearse", h), ("Schedule demo", c)]}]}]},
{"goal": "Buy a laptop for software development.",
 "objectives": [
  {"title": "Define requirements", "projects": [
   {"title": "Requirements", "tasks": [
    ("Define budget", r), ("Define CPU requirements", r), ("Define RAM requirements", r),
    ("Define storage requirements", r)]}]},
  {"title": "Research options", "projects": [
   {"title": "Research", "tasks": [("Research laptops", b), ("Compare specifications", r)]}]},
  {"title": "Compare products", "projects": [
   {"title": "Comparison", "tasks": [("Check reviews", r), ("Check availability", r)]}]},
  {"title": "Purchase", "projects": [
   {"title": "Purchase", "tasks": [
    ("Select according to predefined requirements", r), ("Purchase after confirmation", a)]}]}]},
{"goal": "Prepare my weekly business summary.",
 "objectives": [
  {"title": "Collect updates", "projects": [
   {"title": "Data Collection", "tasks": [("Review projects", r), ("Collect team updates", h)]}]},
  {"title": "Analyze progress", "projects": [
   {"title": "Progress Review", "tasks": [("Check completed tasks", r), ("Check overdue tasks", r)]}]},
  {"title": "Identify blockers", "projects": [
   {"title": "Blockers", "tasks": [("Identify blockers", r), ("Identify important changes", r)]}]},
  {"title": "Prepare summary", "projects": [
   {"title": "Summary", "tasks": [("Prepare summary", c), ("Send summary", a)]}]}]},
{"goal": "Create a repeatable onboarding process for new employees.",
 "objectives": [
  {"title": "Document onboarding", "projects": [
   {"title": "Process Design", "tasks": [("List onboarding steps", r), ("Create checklist", c)]}]},
  {"title": "Prepare resources", "projects": [
   {"title": "Documentation", "tasks": [("Prepare welcome document", c)]}]},
  {"title": "Automate setup", "projects": [
   {"title": "Automation", "tasks": [
    ("Create accounts", h), ("Configure permissions", a), ("Schedule orientation", c)]}]},
  {"title": "Track completion", "projects": [
   {"title": "Tracking", "tasks": [("Assign training", h), ("Track completion", r), ("Collect feedback", h)]}]}]},
{"goal": "Prepare my restaurant for opening.",
 "objectives": [
  {"title": "Prepare location", "projects": [
   {"title": "Location", "tasks": [("Finalize location", a), ("Arrange equipment", h)]}]},
  {"title": "Arrange suppliers", "projects": [
   {"title": "Suppliers", "tasks": [("Find suppliers", r), ("Compare supplier prices", r)]}]},
  {"title": "Hire staff", "projects": [
   {"title": "Staffing", "tasks": [("Hire staff", h), ("Create menus", c)]}]},
  {"title": "Launch marketing", "projects": [
   {"title": "Marketing", "tasks": [
    ("Configure payment systems", a), ("Create website/profile", c), ("Announce opening", a),
    ("Prepare opening day", h)]}]}]},
{"goal": "Create a sustainable weekly fitness routine.",
 "objectives": [
  {"title": "Define goals", "projects": [
   {"title": "Goal Definition", "tasks": [("Define fitness goals", r)]}]},
  {"title": "Create routine", "projects": [
   {"title": "Workout Plan", "tasks": [("Determine available days", r), ("Choose workout types", r)]}]},
  {"title": "Organize schedule", "projects": [
   {"title": "Scheduling", "tasks": [("Create weekly schedule", c), ("Add sessions to calendar", c)]}]},
  {"title": "Track progress", "projects": [
   {"title": "Tracking", "tasks": [("Track completed sessions", r), ("Review progress", r), ("Adjust routine", c)]}]}]},
{"goal": "Plan a family trip for next month.",
 "objectives": [
  {"title": "Choose destination", "projects": [
   {"title": "Destination", "tasks": [("Collect preferences", h), ("Define budget", r), ("Research destinations", r)]}]},
  {"title": "Arrange transportation", "projects": [
   {"title": "Transportation", "tasks": [("Compare transportation", r)]}]},
  {"title": "Book accommodation", "projects": [
   {"title": "Accommodation", "tasks": [("Search hotels", b), ("Check family-friendly activities", r)]}]},
  {"title": "Plan activities", "projects": [
   {"title": "Activities", "tasks": [("Make bookings after approval", a), ("Create itinerary", c)]}]}]},
{"goal": "Create our operating budget for next year.",
 "objectives": [
  {"title": "Analyze historical spending", "projects": [
   {"title": "Historical Analysis", "tasks": [
    ("Collect historical expenses", r), ("Categorize expenses", r), ("Identify recurring costs", r)]}]},
  {"title": "Estimate future costs", "projects": [
   {"title": "Cost Planning", "tasks": [("Estimate hiring costs", r), ("Estimate infrastructure costs", r)]}]},
  {"title": "Define revenue assumptions", "projects": [
   {"title": "Revenue Planning", "tasks": [("Define revenue assumptions", c)]}]},
  {"title": "Build budget", "projects": [
   {"title": "Budget", "tasks": [("Build budget", c), ("Review assumptions", r), ("Finalize budget", a)]}]}]},
{"goal": "Help me recover access to an online account.",
 "objectives": [
  {"title": "Identify account", "projects": [
   {"title": "Account Identification", "tasks": [
    ("Open account recovery page", b), ("Enter approved account identifier", h)]}]},
  {"title": "Start recovery process", "projects": [
   {"title": "Recovery", "tasks": [("Request recovery code", w)]}]},
  {"title": "Complete verification", "projects": [
   {"title": "Verification", "tasks": [
    ("Wait for user-provided code", w), ("Enter code supplied by user", h), ("Reset password", h)]}]},
  {"title": "Restore access", "projects": [
   {"title": "Verification", "tasks": [("Verify login", h), ("Store new credential securely in vault", c)]}]}]},
{"goal": "Schedule a meeting with the investor next week.",
 "objectives": [
  {"title": "Find suitable time", "projects": [
   {"title": "Availability", "tasks": [("Check calendar", c), ("Identify available slots", r)]}]},
  {"title": "Confirm availability", "projects": [
   {"title": "Scheduling", "tasks": [("Check participant availability", h), ("Select matching slot", r)]}]},
  {"title": "Schedule meeting", "projects": [
   {"title": "Confirmation", "tasks": [
    ("Create calendar event", c), ("Add meeting link", c), ("Send invitation", a), ("Confirm meeting", h)]}]}]},
{"goal": "Buy the equipment I selected from the approved website.",
 "objectives": [
  {"title": "Verify product", "projects": [
   {"title": "Product Verification", "tasks": [
    ("Open approved website", b), ("Find product", b), ("Verify model", r),
    ("Verify quantity", r), ("Verify price", r)]}]},
  {"title": "Verify order", "projects": [
   {"title": "Order", "tasks": [
    ("Add to cart", c), ("Review shipping information", r), ("Prepare payment", c)]}]},
  {"title": "Prepare payment", "projects": [
   {"title": "Payment", "tasks": [("Request user approval", a)]}]},
  {"title": "Complete purchase", "projects": [
   {"title": "Confirmation", "tasks": [("Submit payment through secure boundary", a), ("Verify order", r)]}]}]},
{"goal": "Resolve this customer's complaint.",
 "objectives": [
  {"title": "Understand issue", "projects": [
   {"title": "Issue Investigation", "tasks": [("Read customer message", r), ("Identify issue", r)]}]},
  {"title": "Review customer history", "projects": [
   {"title": "Customer History", "tasks": [("Find customer account", r), ("Review previous interactions", r)]}]},
  {"title": "Determine available resolution", "projects": [
   {"title": "Resolution", "tasks": [
    ("Check applicable policy", r), ("Prepare response", c), ("Request approval if necessary", a)]}]},
  {"title": "Respond to customer", "projects": [
   {"title": "Communication", "tasks": [("Send response", a), ("Record resolution", c)]}]}]},
{"goal": "Prepare our weekly sales report.",
 "objectives": [
  {"title": "Collect sales data", "projects": [
   {"title": "Data Collection", "tasks": [("Retrieve sales data", r), ("Calculate total sales", r)]}]},
  {"title": "Analyze performance", "projects": [
   {"title": "Analysis", "tasks": [
    ("Group sales by product", r), ("Group sales by region", r), ("Compare previous week", r),
    ("Identify changes", r)]}]},
  {"title": "Identify changes", "projects": [
   {"title": "Reporting", "tasks": [("Create charts", c)]}]},
  {"title": "Prepare report", "projects": [
   {"title": "Reporting", "tasks": [("Prepare report", c), ("Send report", a)]}]}]},
{"goal": "Set up equipment for our new office.",
 "objectives": [
  {"title": "Determine requirements", "projects": [
   {"title": "Requirements", "tasks": [("Count employees", r), ("Define equipment requirements", r)]}]},
  {"title": "Research products", "projects": [
   {"title": "Product Research", "tasks": [("Research products", b), ("Compare specifications", r)]}]},
  {"title": "Compare options", "projects": [
   {"title": "Comparison", "tasks": [("Check prices", r), ("Check availability", r), ("Create purchase list", c)]}]},
  {"title": "Purchase approved equipment", "projects": [
   {"title": "Procurement", "tasks": [
    ("Request approval", a), ("Place approved orders", a), ("Track deliveries", w)]}]}]},
{"goal": "Create a knowledge base for our customers.",
 "objectives": [
  {"title": "Identify common questions", "projects": [
   {"title": "Question Research", "tasks": [("Analyze support tickets", r), ("Identify common questions", r)]}]},
  {"title": "Organize information", "projects": [
   {"title": "Information Architecture", "tasks": [
    ("Group questions by topic", r), ("Create article structure", c)]}]},
  {"title": "Write documentation", "projects": [
   {"title": "Documentation", "tasks": [
    ("Draft articles", c), ("Review technical accuracy", r), ("Add screenshots", c)]}]},
  {"title": "Publish knowledge base", "projects": [
   {"title": "Publishing", "tasks": [("Publish articles", a), ("Add search", c), ("Monitor unanswered questions", r)]}]}]},
{"goal": "Build the first production-ready MVP of OSOKAI.",
 "objectives": [
  {"title": "Build the agent brain", "projects": [
   {"title": "Brain", "tasks": [
    ("Implement identity", c), ("Implement memory", c), ("Implement goals", c), ("Implement planning", c)]}]},
  {"title": "Build execution infrastructure", "projects": [
   {"title": "Agent Execution", "tasks": [
    ("Implement DecisionEngine", c), ("Implement browser grounding", c), ("Implement orchestrator", c)]}]},
  {"title": "Build user control surfaces", "projects": [
   {"title": "Chrome Extension", "tasks": [
    ("Implement Chrome runtime", c), ("Implement approval system", c)]},
   {"title": "Mobile Control", "tasks": [("Implement mobile approval", c)]}]},
  {"title": "Build security architecture", "projects": [
   {"title": "Security", "tasks": [
    ("Implement durable execution", c), ("Implement recovery", c), ("Implement credential vault", c),
    ("Implement PII shielding", c)]}]},
  {"title": "Test end-to-end workflows", "projects": [
   {"title": "Testing", "tasks": [
    ("Test browser workflows", r), ("Test approval workflows", r), ("Test device disconnect", r),
    ("Test backend restart", r), ("Test credential isolation", r), ("Run end-to-end tests", a)]}]}]},
]


def _words(text: str):
    return set(w for w in re.findall(r"[a-z]{3,}", (text or "").lower()))


def retrieve(goal: str, k: int = 2):
    """Nearest examples: goal-title overlap weighs 3x (intent), objectives 1x (domain)."""
    gw = _words(goal)
    scored = []
    for ex in EXAMPLES:
        g_overlap = len(gw & _words(ex["goal"]))
        o_overlap = len(gw & _words(" ".join(o["title"] for o in ex["objectives"])))
        scored.append((3 * g_overlap + o_overlap, ex))
    scored.sort(key=lambda s: -s[0])
    return [s[1] for s in scored[:k] if s[0] > 0]


def _fmt_example(ex: dict) -> str:
    lines = [f"Goal: {ex['goal']}"]
    for o in ex["objectives"]:
        lines.append(f"Objective: {o['title']}")
        for p in o["projects"]:
            lines.append(f"  Project: {p['title']}")
            for title, kind in p["tasks"]:
                lines.append(f"    - [{kind}] {title}")
    return "\n".join(lines)


def compile_prompt(title: str) -> str:
    """Compile prompt with 2 nearest pack examples injected (few-shot)."""
    shots = "\n\n".join(_fmt_example(ex) for ex in retrieve(title))
    base = ("Decompose this goal into JSON ONLY, no other text. Shape: "
            '{"objectives": [{"title": "...", "projects": [{"title": "...", "tasks": '
            '[{"title": "...", "kind": "research|create|browse|approval|human|wait", '
            '"subtasks": ["..."]}]}]}]}. '
            "5 or fewer objectives, 2-4 tasks per project. "
            "RULE: give a task 2-6 subtasks ONLY if it needs more than one step or touches "
            "the outside world (calendar, email, browser, people, payments). "
            "Atomic single actions (open a site, look something up) get NO subtasks. "
            "RULE: passwords/credentials stay behind the vault (human kind, never plaintext); "
            "money moves only with approval kind.")
    if shots:
        base += "\n\nFollow the pattern of these examples:\n\n" + shots
    return base + f"\n\nGoal: {title}"
