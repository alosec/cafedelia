# Elia Database and Chat Rendering Analysis

This document summarizes the database architecture and chat rendering process of the Elia project, which serves as the foundation for `cafedelia`.

## Database System

Elia uses an asynchronous **SQLite** database, managed via `SQLModel` and `SQLAlchemy`.

-   **Database File**: `elia.sqlite`
-   **Core Logic**: `elia_chat/database/database.py` handles the database connection and session management.
-   **Schema Definition**: `elia_chat/database/models.py` defines the data models.
    -   **`ChatDao`**: Represents a chat conversation.
    -   **`MessageDao`**: Represents a single message within a chat.

## Chat Registration Flow

1.  **Chat Creation**: `ChatsManager.create_chat` creates a new `ChatDao` and persists the initial messages as `MessageDao` objects.
2.  **Adding Messages**:
    -   User messages are added to the database immediately via `ChatsManager.add_message_to_chat`.
    -   Assistant messages are saved to the database after the full response has been streamed.

## UI Rendering

The UI is built with Textual.

1.  **`ChatScreen`**: The main screen for a chat session, which contains the `Chat` widget.
2.  **`Chat` Widget**: Manages the display of the conversation.
3.  **`Chatbox` Widget**: Renders an individual message bubble.

## Data Handling: Historical vs. Streaming

-   **Historical Chats**: When an existing chat is opened, all messages are fetched from the database at once and rendered using `Chatbox` widgets.
-   **Live Streaming**: For new messages, a background thread streams the response from the AI model. A `Chatbox` widget is updated in real-time as data chunks arrive, and the final message is saved to the database upon completion.
