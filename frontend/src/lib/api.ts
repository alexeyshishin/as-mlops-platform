
const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "https://api.alexshishin.ru").replace(
  /\/+$/,
  "",
);

export type HistoryTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ClassifyRequest = {
  sessionId?: string;
  userId?: string | null;
  history?: HistoryTurn[];
  text: string;
};


export type ClassifyResponse = {
  confidence?: number;
  intent?: string;
  [key: string]: unknown;
};

export type Dialog = {
  session_id: string;
  seq: number;
  label: string;
  created_at: string;
};

export type DialogMeta = Dialog & {
  intents_recognized: number;
};

export type DialogTurn = {
  text: string;
  intent: string | null;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ApiError";
  }
}

export async function classify({
  sessionId,
  userId,
  history,
  text,
}: ClassifyRequest): Promise<ClassifyResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, user_id: userId, history, text }),
    });
  } catch (cause) {
    throw new ApiError(
      "Не удалось связаться с сервером — проверьте сеть или CORS-настройки backend.",
      undefined,
      { cause },
    );
  }

  if (!response.ok) {
    throw new ApiError(`Сервер ответил ошибкой ${response.status}`, response.status);
  }

  return response.json();
}

export async function getDialogTurns(
  sessionId: string,
): Promise<{ session_id: string; turns: DialogTurn[] }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/dialogs/${sessionId}/turns`);
  } catch (cause) {
    throw new ApiError(
      "Не удалось связаться с сервером — проверьте сеть или CORS-настройки backend.",
      undefined,
      { cause },
    );
  }

  if (!response.ok) {
    throw new ApiError(`Сервер ответил ошибкой ${response.status}`, response.status);
  }

  return response.json();
}

export async function listDialogs(userId: string): Promise<Dialog[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/dialogs?user_id=${encodeURIComponent(userId)}`);
  } catch (cause) {
    throw new ApiError(
      "Не удалось связаться с сервером — проверьте сеть или CORS-настройки backend.",
      undefined,
      { cause },
    );
  }

  if (!response.ok) {
    throw new ApiError(`Сервер ответил ошибкой ${response.status}`, response.status);
  }

  const data: { dialogs: Dialog[] } = await response.json();
  return data.dialogs;
}

export async function deleteDialog(sessionId: string, userId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/dialogs/${sessionId}?user_id=${encodeURIComponent(userId)}`,
      { method: "DELETE" },
    );
  } catch (cause) {
    throw new ApiError(
      "Не удалось связаться с сервером — проверьте сеть или CORS-настройки backend.",
      undefined,
      { cause },
    );
  }

  if (response.status === 404) return;
  if (!response.ok) {
    throw new ApiError(`Сервер ответил ошибкой ${response.status}`, response.status);
  }
}

export async function getDialog(sessionId: string): Promise<DialogMeta> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/dialogs/${sessionId}`);
  } catch (cause) {
    throw new ApiError(
      "Не удалось связаться с сервером — проверьте сеть или CORS-настройки backend.",
      undefined,
      { cause },
    );
  }

  if (!response.ok) {
    throw new ApiError(`Сервер ответил ошибкой ${response.status}`, response.status);
  }

  return response.json();
}
