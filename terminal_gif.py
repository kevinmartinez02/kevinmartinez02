import gifos

GREEN = "\x1b[92m"
BLUE = "\x1b[94m"
YELLOW = "\x1b[93m"
CYAN = "\x1b[96m"
RESET = "\x1b[0m"

PROMPT = f"{GREEN}kevin@github{RESET}:{BLUE}~{RESET}$ "

t = gifos.Terminal(750, 500, 15, 15)
t.toggle_show_cursor(True)

t.gen_typing_text(f"{PROMPT}whoami", 1)
t.gen_text(f"{CYAN}Kevin Alfredo Martínez{RESET} - Full Stack Developer", 2)
t.clone_frame(15)

t.gen_typing_text(f"{PROMPT}cat about.txt", 4)
t.gen_text("Building scalable, secure and maintainable web apps.", 5)
t.gen_text("Backend services & modern UIs. REST APIs, database", 6)
t.gen_text("design, auth, integrations, client-server architecture.", 7)
t.gen_text(f"{YELLOW}NestJS · Django · Next.js · Node.js · PostgreSQL · Docker{RESET}", 8)
t.clone_frame(25)

t.gen_typing_text(f"{PROMPT}cat contact.txt", 10)
t.gen_text(f"LinkedIn : {BLUE}linkedin.com/in/kevin-martinez-50a592330{RESET}", 11)
t.gen_text(f"Email    : {BLUE}kemart1230@gmail.com{RESET}", 12)
t.clone_frame(20)

t.gen_typing_text(f"{PROMPT}", 14)
t.clone_frame(40)

t.gen_gif()
