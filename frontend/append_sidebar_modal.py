import re

with open('frontend/src/components/Sidebar.svelte', 'r') as f:
    text = f.read()

modal_styles = """
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(28,24,20,0.4);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    padding: 24px;
    font-family: var(--font-sans);
  }

  .modal {
    background: #FAF8F4;
    border: 0.5px solid #D4CEBC;
    padding: 24px;
    border-radius: 24px;
    max-width: 400px;
    width: 100%;
    animation: dropIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .modal h3 {
    margin: 0 0 8px;
    font-size: 18px;
    font-weight: 500;
    color: #1C1814;
  }

  .modal p {
    margin: 0 0 24px;
    font-size: 14px;
    color: #4A4237;
    line-height: 1.5;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .btn-cancel {
    padding: 8px 16px;
    background: transparent;
    border: 0.5px solid #D4CEBC;
    border-radius: 12px;
    color: #1C1814;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }
  .btn-cancel:hover { background: #EEEAE1; }

  .btn-delete {
    padding: 8px 16px;
    background: #F5EAE0;
    border: 0.5px solid rgba(201,124,74,0.25);
    border-radius: 12px;
    color: #C97C4A;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
  }
  .btn-delete:hover { background: #EEEAE1; }

  .delete-btn { /* The trash icon button on the item */
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
    border-radius: 6px;
    background: transparent;
    border: none;
    color: #8C8070;
    cursor: pointer;
    opacity: 0;
    transition: all 0.15s ease;
  }
  .session-item:hover .delete-btn { opacity: 1; }
  .delete-btn:hover { color: #C97C4A; background: rgba(201,124,74,0.1); }
"""

# Append to the end of the <style> block
text = re.sub(r'</style>(?!.*</style>)', f'{modal_styles}\n</style>', text, flags=re.DOTALL)

# Cleanup the mistake of adding duplicate <style> at EOF from previous command
text = re.sub(r'<style>\s*/\* Base sidebar.*?</style>', '', text, flags=re.DOTALL)

with open('frontend/src/components/Sidebar.svelte', 'w') as f:
    f.write(text)

