import os
import re


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # We want to find className="..." that contains "bg-card" and add "stagger-card" if not present
    # This regex looks for className="<anything>bg-card<anything>"

    def replacement(match):
        class_content = match.group(1)
        if 'stagger-card' not in class_content:
            return f'className="{class_content} stagger-card"'
        return match.group(0)

    # Match className="..." attributes containing bg-card
    new_content = re.sub(r'className="([^"]*bg-card[^"]*)"', replacement, content)

    # Also handle backticks in className={`...`}
    def backtick_replacement(match):
        class_content = match.group(1)
        if 'stagger-card' not in class_content:
            return f'className={{`{class_content} stagger-card`}}'
        return match.group(0)

    new_content = re.sub(r'className=\{`([^`]*bg-card[^`]*)`\}', backtick_replacement, new_content)

    if content != new_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

def main():
    pages_dir = os.path.join("frontend", "src", "pages")
    for root, _, files in os.walk(pages_dir):
        for file in files:
            if file.endswith('.tsx'):
                process_file(os.path.join(root, file))

if __name__ == '__main__':
    main()
