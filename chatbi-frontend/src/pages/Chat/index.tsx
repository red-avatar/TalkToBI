import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactECharts from 'echarts-for-react';
import {
  Send,
  Link,
  Unlink,
  Trash2,
  Code,
  Bug,
  ChevronDown,
  ChevronUp,
  Sparkles,
  User,
} from 'lucide-react';
import { Card, Button, Badge, Spinner } from '../../components/ui';
import { useChat } from '../../hooks/useChat';
import type { ChatMessage } from '../../hooks/useChat';
import * as styles from './styles.css';

// 工具函数：将毫秒转换为秒
const msToSeconds = (ms: number) => (ms / 1000).toFixed(2);

const Chat: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const [expandedSql, setExpandedSql] = useState<string | null>(null);
  const [expandedDebug, setExpandedDebug] = useState<string | null>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { messages, isConnected, isLoading, sessionId, connect, disconnect, sendMessage, clearMessages } = useChat();

  useEffect(() => {
    if (messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (inputValue.trim() && isConnected && !isLoading) {
      sendMessage(inputValue);
      setInputValue('');
      // 保持输入框焦点
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const renderMessageContent = (msg: ChatMessage) => {
    if (msg.role === 'user') {
      return <p className={styles.messageText}>{msg.content}</p>;
    }

    return (
      <div className={styles.assistantContent}>
        <p className={styles.messageText}>
          {msg.isStreaming && <Spinner size="sm" className={styles.inlineSpinner} />}
          {msg.content}
        </p>

        {/* Highlights */}
        {msg.highlights && msg.highlights.length > 0 && (
          <div className={styles.highlights}>
            {msg.highlights.map((h, i) => (
              <Badge key={i} variant="primary" size="sm">{h}</Badge>
            ))}
          </div>
        )}

        {/* SQL Code Block */}
        {msg.sqlQuery && (
          <div className={styles.codeSection}>
            <button
              className={styles.sectionToggle}
              onClick={() => setExpandedSql(expandedSql === msg.id ? null : msg.id)}
            >
              <Code size={16} />
              <span>执行的 SQL</span>
              {expandedSql === msg.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            <AnimatePresence>
              {expandedSql === msg.id && (
                <motion.pre
                  className={styles.codeBlock}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                >
                  {msg.sqlQuery}
                </motion.pre>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Data Table - 当chart_type为table时显示全部数据，否则显示前5行 */}
        {msg.visualization?.raw_data && msg.visualization.raw_data.length > 0 && (
          <div className={styles.tableWrapper}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  {Object.keys(msg.visualization.raw_data[0]).map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(msg.visualization.chart_type === 'table' 
                  ? msg.visualization.raw_data 
                  : msg.visualization.raw_data.slice(0, 5)
                ).map((row, idx) => (
                  <tr key={idx}>
                    {Object.values(row).map((val, i) => (
                      <td key={i}>{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {msg.visualization.chart_type !== 'table' && msg.visualization.raw_data.length > 5 && (
              <p className={styles.tableMore}>共 {msg.visualization.raw_data.length} 条数据</p>
            )}
          </div>
        )}

        {/* Chart */}
        {msg.visualization?.echarts_option && (
          <Card variant="glass" padding="sm" className={styles.chartCard}>
            <ReactECharts 
              option={{
                ...msg.visualization.echarts_option,
                backgroundColor: 'transparent',
              }} 
              style={{ height: 280 }} 
            />
          </Card>
        )}

        {/* Debug Info */}
        {msg.debug && (msg.debug.intent || msg.debug.sql_query) && (
          <div className={styles.codeSection}>
            <button
              className={styles.sectionToggle}
              onClick={() => setExpandedDebug(expandedDebug === msg.id ? null : msg.id)}
            >
              <Bug size={16} />
              <span>调试信息</span>
              {expandedDebug === msg.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            <AnimatePresence>
              {expandedDebug === msg.id && (
                <motion.div
                  className={styles.debugContent}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                >
                  {msg.debug.intent && (
                    <div>
                      <span className={styles.debugLabel}>意图解析:</span>
                      <pre className={styles.codeBlock}>{JSON.stringify(msg.debug.intent, null, 2)}</pre>
                    </div>
                  )}
                  {msg.debug.execution_time_ms !== undefined && (
                    <p className={styles.debugLabel}>执行时间: {msToSeconds(msg.debug.execution_time_ms)}s</p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerMain}>
          <div className={styles.headerLeft}>
            <Sparkles size={24} className={styles.headerIcon} />
            <div className={styles.headerTitleGroup}>
              <h2 className={styles.title}>智能对话</h2>
              <span className={styles.sessionId}>会话 ID: {sessionId.slice(0, 8)}</span>
            </div>
          </div>
          <div className={styles.headerCenter}>
            <Badge variant={isConnected ? 'success' : 'error'} dot>
              {isConnected ? '服务已连接' : '服务未连接'}
            </Badge>
          </div>
          <div className={styles.headerRight}>
            {isConnected ? (
              <Button variant="ghost" size="sm" leftIcon={<Unlink size={16} />} onClick={disconnect}>
                断开连接
              </Button>
            ) : (
              <Button variant="primary" size="sm" leftIcon={<Link size={16} />} onClick={connect}>
                连接服务
              </Button>
            )}
            <Button variant="ghost" size="sm" leftIcon={<Trash2 size={16} />} onClick={clearMessages}>
              清空对话
            </Button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className={styles.messageList} ref={messageListRef}>
        {messages.length === 0 ? (
          <div className={styles.emptyState}>
            <Sparkles size={48} className={styles.emptyIcon} />
            <p>开始与 TalktoBI 对话，探索数据洞察</p>
          </div>
        ) : (
          <AnimatePresence>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                className={styles.messageItem({ isUser: msg.role === 'user' })}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
              >
                <div className={styles.avatar({ isUser: msg.role === 'user' })}>
                  {msg.role === 'user' ? <User size={18} /> : <Sparkles size={18} />}
                </div>
                <div className={styles.messageBubble({ isUser: msg.role === 'user' })}>
                  {renderMessageContent(msg)}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* Fixed Bottom Input */}
      <div className={styles.inputArea}>
        <div className={styles.inputWrapper}>
          <textarea
            ref={inputRef}
            className={styles.input}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={isConnected ? '输入您的问题，例如：今年销售额最高的产品是什么？' : '请先连接服务...'}
            disabled={!isConnected || isLoading}
            rows={1}
          />
          <Button
            className={styles.sendButton}
            leftIcon={isLoading ? <Spinner size="sm" /> : <Send size={18} />}
            onClick={handleSend}
            disabled={!isConnected || !inputValue.trim() || isLoading}
          >
            发送
          </Button>
        </div>
        <p className={styles.inputHint}>
          按 Enter 发送，Shift + Enter 换行
        </p>
      </div>
    </div>
  );
};

export default Chat;
