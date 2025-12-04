import { useState, useRef, useCallback, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { 
  WSMessage, 
  WSStatusPayload, 
  WSCompletePayload, 
  WSErrorPayload,
  WSVisualizationPayload,
  WSDebugPayload,
  ProcessingStage
} from '../api/types';

// 阶段描述映射
const STAGE_DESCRIPTIONS: Record<ProcessingStage, string> = {
  intent: '🔍 正在理解您的问题...',
  planner: '📝 正在生成查询方案...',
  executor: '⚡ 正在执行数据查询...',
  analyzer: '📊 正在分析数据...',
  responder: '💬 正在生成回答...',
};

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  stage?: ProcessingStage;
  // 完成后的数据
  sqlQuery?: string;
  visualization?: WSVisualizationPayload;
  debug?: WSDebugPayload;
  highlights?: string[];
  error?: string;
}

interface UseChatOptions {
  onError?: (error: string) => void;
}

export function useChat(options?: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => uuidv4());
  
  const wsRef = useRef<WebSocket | null>(null);
  const currentMessageIdRef = useRef<string | null>(null);

  // 获取WebSocket URL
  const getWsUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    return `${protocol}//${host}/api/v1/ws/chat/${sessionId}`;
  }, [sessionId]);

  // 更新当前助手消息
  const updateCurrentMessage = useCallback((updates: Partial<ChatMessage>) => {
    const msgId = currentMessageIdRef.current;
    if (!msgId) return;
    
    setMessages(prev => prev.map(m => 
      m.id === msgId ? { ...m, ...updates } : m
    ));
  }, []);

  // 处理状态消息
  const handleStatus = useCallback((payload: WSStatusPayload) => {
    const desc = STAGE_DESCRIPTIONS[payload.stage] || payload.message;
    updateCurrentMessage({ 
      content: desc, 
      stage: payload.stage 
    });
  }, [updateCurrentMessage]);

  // 处理完成消息
  const handleComplete = useCallback((payload: WSCompletePayload) => {
    updateCurrentMessage({
      content: payload.text_answer,
      isStreaming: false,
      sqlQuery: payload.sql_query,
      visualization: payload.visualization,
      debug: payload.debug,
      highlights: payload.data_insight?.highlights,
    });
    setIsLoading(false);
    currentMessageIdRef.current = null;
  }, [updateCurrentMessage]);

  // 处理错误消息
  const handleError = useCallback((payload: WSErrorPayload) => {
    updateCurrentMessage({
      content: `错误: ${payload.message}`,
      isStreaming: false,
      error: payload.message,
    });
    setIsLoading(false);
    currentMessageIdRef.current = null;
    options?.onError?.(payload.message);
  }, [updateCurrentMessage, options]);

  // 处理收到的消息
  const handleMessage = useCallback((msg: WSMessage) => {
    console.log('[WS] Received:', msg.type, msg.payload);
    
    switch (msg.type) {
      case 'status':
        handleStatus(msg.payload as WSStatusPayload);
        break;
        
      case 'text_chunk':
        // 流式文本块 - 追加到当前消息
        const chunk = msg.payload as { content: string };
        setMessages(prev => prev.map(m => 
          m.id === currentMessageIdRef.current
            ? { ...m, content: m.content + chunk.content }
            : m
        ));
        break;
        
      case 'complete':
        handleComplete(msg.payload as WSCompletePayload);
        break;
        
      case 'error':
        handleError(msg.payload as WSErrorPayload);
        break;
        
      case 'interrupted':
        updateCurrentMessage({
          content: '查询已中断',
          isStreaming: false,
        });
        setIsLoading(false);
        currentMessageIdRef.current = null;
        break;
        
      case 'pong':
        console.log('[WS] Pong received');
        break;
        
      default:
        console.log('[WS] Unknown message type:', msg.type);
    }
  }, [handleStatus, handleComplete, handleError, updateCurrentMessage]);

  // 连接WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('[WS] Connected to', getWsUrl());
    };

    ws.onclose = (e) => {
      setIsConnected(false);
      console.log('[WS] Disconnected:', e.code, e.reason);
    };

    ws.onerror = (e) => {
      console.error('[WS] Error:', e);
      options?.onError?.('WebSocket连接错误');
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.error('[WS] Parse error:', e);
      }
    };
  }, [getWsUrl, handleMessage, options]);

  // 发送消息
  const sendMessage = useCallback((content: string) => {
    if (!content.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const clientMessageId = `msg_${uuidv4().replace(/-/g, '').slice(0, 12)}`;

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: uuidv4(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    // 创建助手消息占位
    const assistantMsgId = uuidv4();
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '正在分析...',
      timestamp: new Date(),
      isStreaming: true,
    };
    currentMessageIdRef.current = assistantMsgId;
    setMessages(prev => [...prev, assistantMsg]);
    setIsLoading(true);

    // 发送符合后端协议的消息
    const wsMessage = {
      type: 'user_message',
      payload: {
        content: content.trim(),
        message_id: clientMessageId,
      }
    };
    
    console.log('[WS] Sending:', wsMessage);
    wsRef.current.send(JSON.stringify(wsMessage));
  }, []);

  // 发送中断请求
  const interrupt = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    
    wsRef.current.send(JSON.stringify({
      type: 'interrupt',
      payload: {
        reason: 'user_cancel'
      }
    }));
  }, []);

  // 断开连接
  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  // 清空消息
  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  // 组件卸载时断开连接
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    messages,
    isConnected,
    isLoading,
    sessionId,
    connect,
    disconnect,
    sendMessage,
    clearMessages,
    interrupt,
  };
}
