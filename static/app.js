document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const hero = document.getElementById('hero');
    const suggestions = document.getElementById('suggestions');
    const mainEl = document.querySelector('.main');

    let isProcessing = false;

    // Suggestion chip clicks
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const question = chip.dataset.question;
            if (question && !isProcessing) {
                chatInput.value = question;
                handleSend();
            }
        });
    });

    // Form submit
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (!isProcessing) handleSend();
    });

    async function handleSend() {
        const message = chatInput.value.trim();
        if (!message) return;

        isProcessing = true;
        sendBtn.disabled = true;
        chatInput.value = '';

        // Hide hero and suggestions on first message
        if (hero && !hero.classList.contains('hidden')) {
            hero.classList.add('hidden');
            suggestions.classList.add('hidden');
            mainEl.classList.add('chatting');
        }

        // Add user message
        appendMessage('user', message);

        // Show typing indicator
        const typingEl = showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            });

            const data = await response.json();
            removeTypingIndicator(typingEl);
            appendMessage('assistant', data.answer);

        } catch (error) {
            removeTypingIndicator(typingEl);
            appendMessage('assistant', 'A apărut o eroare la conectarea cu serverul. Verifică dacă serverul rulează.');
        }

        isProcessing = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }

    function appendMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', role);

        const avatar = document.createElement('div');
        avatar.classList.add('message-avatar');
        avatar.textContent = role === 'user' ? 'Tu' : 'AI';

        const bubble = document.createElement('div');
        bubble.classList.add('message-bubble');
        bubble.textContent = text;

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);

        // Scroll to bottom
        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }

    function showTypingIndicator() {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'assistant');

        const avatar = document.createElement('div');
        avatar.classList.add('message-avatar');
        avatar.textContent = 'AI';

        const bubble = document.createElement('div');
        bubble.classList.add('message-bubble', 'typing-indicator');
        bubble.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(bubble);
        chatMessages.appendChild(messageDiv);

        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'end' });
        return messageDiv;
    }

    function removeTypingIndicator(el) {
        if (el && el.parentNode) {
            el.parentNode.removeChild(el);
        }
    }
});
