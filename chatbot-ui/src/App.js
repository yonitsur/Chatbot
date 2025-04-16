import React, {useState, useRef, useEffect, useCallback} from 'react';
import {v4 as uuidv4} from 'uuid';
import {format} from 'date-fns';
import './App.css';
import ReactMarkdown from 'react-markdown';

function App() {
    const [inputText, setInputText] = useState('');
    const [messages, setMessages] = useState([]);
    const [userId, setUserId] = useState('');
    const [userNameInput, setUserNameInput] = useState('');
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [isSending, setIsSending] = useState(false);


    const [sessions, setSessions] = useState([]);
    const [activeSessionId, setActiveSessionId] = useState(null);
    const [isLoadingSessions, setIsLoadingSessions] = useState(false);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [darkMode, setDarkMode] = useState(false);

    const chatContainerRef = useRef(null);

    const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';
    const appName = "VentureMind";

    const toggleDarkMode = () => {
        setDarkMode(prevMode => !prevMode);
    };

    const sessionsUrl = (uId) => `${backendUrl}/sessions/${uId}`;
    const historyUrl = (uId, sId) => `${backendUrl}/history/${uId}/${sId}`;
    const queryUrl = `${backendUrl}/query`;


    const handleInputChange = (event) => {
        setInputText(event.target.value);
    };

    const handleUserNameInputChange = (event) => {
        setUserNameInput(event.target.value);
    };


    const handleLogin = (event) => {
        event.preventDefault();
        if (userNameInput.trim()) {
            const trimmedUserId = userNameInput.trim();
            setUserId(trimmedUserId);
            setIsLoggedIn(true);
            setMessages([]);
            setActiveSessionId(null);

            fetchSessions(trimmedUserId);
        }
    };


    const handleSessionSelect = useCallback(async (sessionId, currentUserId) => {


        if (!currentUserId || !sessionId) {
            console.warn("User ID or Session ID missing for selection.");
            return;
        }
        ;

        console.log(`Selecting session: ${sessionId} for user: ${currentUserId}`);
        setActiveSessionId(sessionId);
        setIsLoadingHistory(true);
        setMessages([]);

        try {
            const response = await fetch(historyUrl(currentUserId, sessionId));
            if (!response.ok) {
                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || JSON.stringify(errorData);
                } catch (parseError) {
                }
                throw new Error(errorDetail);
            }
            const data = await response.json();
            const historyMessages = data.messages.map(msg => ({

                text: msg.message,
                sender: msg.role === 'user' ? 'user' : 'bot',
                error: msg.status === 'error'
            }));
            setMessages(historyMessages);
        } catch (error) {
            console.error("Error fetching history:", error);
            setMessages([{text: `Error loading chat history: ${error.message}`, sender: 'bot', error: true}]);
        } finally {
            setIsLoadingHistory(false);
        }

    }, []);


    const fetchSessions = useCallback(async (currentUserId) => {
        if (!currentUserId) return;
        setIsLoadingSessions(true);
        console.log(`Workspaceing sessions for user: ${currentUserId}`);
        try {
            const fetchUrl = sessionsUrl(currentUserId);
            console.log(`Workspaceing sessions for user: ${currentUserId} from URL: ${fetchUrl}`);
            const response = await fetch(fetchUrl);


            console.log(`Response Status Code: ${response.status}`);
            console.log(`Response 'ok' property: ${response.ok}`);
            console.log(`Response Content-Type header: ${response.headers.get('Content-Type')}`);

            const rawText = await response.text();
            console.log(`Raw response text received (first 100 chars): ${rawText.substring(0, 100)}...`);
            console.log(`Raw response text : ${rawText}`);

            if (!response.ok) {

                throw new Error(`HTTP error! status: ${response.status}, body: ${rawText}`);
            }


            const data = JSON.parse(rawText);


            setSessions(data.sessions || []);

            if (data.sessions && data.sessions.length > 0) {
                handleSessionSelect(data.sessions[0].session_id, currentUserId);
            } else {
                setActiveSessionId(null);
                setMessages([{text: `Welcome, ${currentUserId}! Start a new chat by typing below.`, sender: 'bot'}]);
            }
        } catch (error) {

            console.error("Error caught in fetchSessions:", error);
            setMessages([{text: `Error fetching your sessions: ${error.message}`, sender: 'bot', error: true}]);
            setSessions([]);
        } finally {
            setIsLoadingSessions(false);
        }


    }, [handleSessionSelect]);


    const handleNewChat = () => {
        setActiveSessionId(null);
        setMessages([{text: "Hey! Ask me anything about startups!", sender: 'bot'}]);
        setInputText('');
    };


    const handleSendMessage = async () => {
        const userMessageText = inputText.trim();

        if (!userMessageText || isSending || !isLoggedIn || !userId || isLoadingHistory) {
            return;
        }

        setIsSending(true);
        setInputText('');

        let currentSessionId = activeSessionId;
        let isNewSession = false;


        if (!currentSessionId) {
            currentSessionId = uuidv4();
            setActiveSessionId(currentSessionId);
            isNewSession = true;
            console.log(`Starting new session: ${currentSessionId}`);


            setMessages((prevMessages) => [
                ...prevMessages.filter(m => !(m.sender === 'bot' && (m.text.includes("Starting a new chat") || m.text.includes("Welcome,")))),
                {text: userMessageText, sender: 'user'}
            ]);
        } else {

            setMessages((prevMessages) => [...prevMessages, {text: userMessageText, sender: 'user'}]);
        }


        const payload = {
            message: userMessageText,
            user_id: userId,
            session_id: currentSessionId,
        };

        console.log("Sending payload:", JSON.stringify(payload));
        console.log("queryUrl:", queryUrl);

        try {
            const response = await fetch(queryUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload),
            });


            if (response.status === 202) {

                const data = await response.json();
                console.warn("Message skipped by server:", data.output);


                setMessages((prevMessages) => prevMessages.filter(m => !(m.sender === 'user' && m.text === userMessageText)));


            } else if (!response.ok) {

                let errorDetail = `HTTP error! status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || JSON.stringify(errorData);
                } catch (parseError) {
                }

                setMessages((prevMessages) => prevMessages.filter(m => !(m.sender === 'user' && m.text === userMessageText)));
                throw new Error(errorDetail);
            } else {

                const data = await response.json();
                const botResponseMessage = {text: data.output, sender: 'bot'};


                setMessages((prevMessages) => [...prevMessages, botResponseMessage]);


                if (isNewSession) {
                    console.log("New session created, refreshing session list...");

                    setTimeout(() => fetchSessions(userId), 500);
                }
            }

        } catch (error) {
            console.error('Error sending message:', error);

            const errorMessage = {text: `Error: ${error.message}`, sender: 'bot', error: true};
            setMessages((prevMessages) => [...prevMessages, errorMessage]);

            if (isNewSession) {
                setActiveSessionId(null);

                setMessages([{text: "Failed to start the new session. Please try again.", sender: 'bot', error: true}]);
            }
        } finally {
            setIsSending(false);
        }
    };


    useEffect(() => {
        if (chatContainerRef.current) {


            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [messages]);


    if (!isLoggedIn) {
        return (
            <div className={`app-container ${darkMode ? 'dark-mode' : ''} login-view`}>
                <div className="login-container">
                    <h1>Welcome to {appName}</h1>
                    <p>Your AI assistant for startup and VC insights.</p>
                    <form onSubmit={handleLogin}>
                        <input
                            type="text"
                            value={userNameInput}
                            onChange={handleUserNameInputChange}
                            placeholder="Enter your name"
                            required
                            autoFocus
                        />
                        <button type="submit">Enter Chat</button>
                    </form>
                    {}
                    <button className="theme-toggle" onClick={toggleDarkMode}>
                        {darkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className={`app-container ${darkMode ? 'dark-mode' : ''}`}>
            <div className="sidebar">
                <div className="sidebar-header">
                    <button onClick={handleNewChat} className="new-chat-button">
                        + New Chat
                    </button>
                </div>
                <div className="sidebar-title">Recent Chats</div>
                {isLoadingSessions ? (
                    <div className="sidebar-loading">Loading sessions...</div>
                ) : sessions.length === 0 ? (
                    <div className="sidebar-empty">No past sessions found.</div>
                ) : (
                    <ul className="sessions-list">
                        {sessions.map((session) => (
                            <li
                                key={session.session_id}
                                className={`session-item ${session.session_id === activeSessionId ? 'active' : ''}`}
                                onClick={() => handleSessionSelect(session.session_id, userId)}
                            >
                                Chat Session
                                <span>
                        {format(new Date(session.start_time), 'MMM d, yyyy h:mm a')}
                    </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="chat-area">
                <div className="chat-window">
                    <div className="chat-header">
                        <h1>{appName}</h1>
                        <span>
              User: {userId} {activeSessionId ? `(Session: ${activeSessionId.substring(0, 8)}...)` : '(New Chat)'}
            </span>
                        {}
                        <button className="theme-toggle" onClick={toggleDarkMode}>
                            {darkMode ? "Light Mode" : "Dark Mode"}
                        </button>
                    </div>
                    <div
                        className={`chat-container ${isLoadingHistory ? 'loading' : ''} ${!activeSessionId && messages.length <= 1 ? 'no-session' : ''}`}
                        ref={chatContainerRef}
                    >
                        {isLoadingHistory ? (
                            <div>Loading chat history...</div>
                        ) : !activeSessionId && messages.length <= 1 && messages.some(m => m.text.includes("Start a new chat")) ? (
                            <div>Select a session or start a new chat!</div>
                        ) : (
                            messages.map((message, index) => (
                                <div key={index}
                                     className={`message ${message.sender} ${message.error ? 'error' : ''}`}>
                                    {message.sender === 'bot' ? (
                                        <ReactMarkdown>{message.text || ''}</ReactMarkdown>
                                    ) : (
                                        message.text
                                    )}
                                </div>
                            ))
                        )}
                        {isSending && !isLoadingHistory && (
                            <div className="message bot typing">
                                <span>.</span><span>.</span><span>.</span>
                            </div>
                        )}
                    </div>
                    <div className="input-container">
                        <input
                            type="text"
                            value={inputText}
                            onChange={handleInputChange}
                            placeholder={isSending ? "Waiting for response..." : isLoadingHistory ? "Loading history..." : "Ask anything..."}
                            onKeyPress={(event) => event.key === 'Enter' && handleSendMessage()}
                            disabled={isSending || isLoadingHistory || !userId}
                        />
                        <button
                            onClick={handleSendMessage}
                            disabled={isSending || isLoadingHistory || !userId || !inputText.trim()}
                        >
                            {isSending ? 'Sending...' : 'Send'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default App;