import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Zap, Mic, Settings, Trash2,
  Cpu, Server, Send, Loader, Plus
} from 'lucide-react';
import { useLlmChat } from '@/hooks/useLlmChat';

export function AgentChatPage() {
  const { t: _t } = useTranslation();

  const { messages, loading, error, sendMessage, clearChat } = useLlmChat(
    "engineer_assistant",
  );

  const [inputValue, setInputValue] = useState('');
  const [isListening, setIsListening] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const quickCommands = [
    'فحص الامتثال',
    'حساب الحمل',
    'دراسة القوس الكهربائي',
    'تحديد حجم الكابل',
    'تحليل التيار القصير',
    'دراسة التنسيق',
    'إنشاء مخطط',
    'تصدير التقرير'
  ];

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || loading) return;
    const content = inputValue;
    setInputValue('');
    void sendMessage(content);
  };

  const handleQuickCommand = (command: string) => {
    setInputValue(command);
  };

  const handleClearHistory = () => {
    clearChat();
  };

  const isConnected = !loading && !error;

  // Status bar helpers - extracted to avoid nested ternaries (S3358)
  const statusTextClass = isConnected ? 'text-emerald-500' : error ? 'text-destructive' : 'text-muted-foreground';
  const statusDotClass = `w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-500' : error ? 'bg-destructive' : 'bg-muted-foreground animate-pulse'}`;
  const statusText = loading ? 'Connecting...' : error ? 'Offline' : 'Connected';

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      {/* Header */}
      <div className="h-16 border-b border-border flex items-center justify-between px-6 bg-card stagger-card">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-secondary to-secondary/60 flex items-center justify-center border border-secondary/50">
            <Zap className="h-5 w-5 text-secondary-foreground" />
          </div>
          <div>
            <h1 className="font-semibold text-base text-foreground">FireAI Assistant</h1>
            <p className="text-xs text-muted-foreground">مساعد هندسي ذكي (استشاري — تحقق من المخرجات)</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            className="h-9 w-9 border-border hover:bg-muted"
            onClick={handleClearHistory}
            title="مسح المحادثة"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-9 w-9 border-border hover:bg-muted"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Chat Area */}
      <ScrollArea className="flex-1 p-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-16">
              <Zap className="h-10 w-10 mx-auto text-secondary/60 mb-4" />
              <p className="text-sm text-muted-foreground">
                ابدأ محادثة مع المساعد الهندسي. المخرجات استشارية وتخضع للتحقق من مهندس مرخص.
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={`${message.timestamp}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {message.role === 'assistant' && (
                <div className="w-8 h-8 rounded bg-secondary/20 flex items-center justify-center border border-secondary/50 shrink-0 mr-3">
                  <Zap className="h-4 w-4 text-secondary" />
                </div>
              )}

              <div className={`max-w-md ${message.role === 'user' ? 'order-2 ml-3' : ''}`}>
                <div className={`px-4 py-3 rounded-xl ${
                  message.role === 'user'
                    ? 'bg-secondary/20 text-foreground border border-secondary/30 rounded-br-none'
                    : 'bg-muted text-foreground border border-border rounded-bl-none'
                }`}>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                </div>

                {message.role === 'assistant' && (message.source || message.model) && (
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {message.source && (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground bg-transparent border-border">
                        {message.source}
                      </Badge>
                    )}
                    {message.model && (
                      <Badge variant="outline" className="text-[10px] text-muted-foreground bg-transparent border-border">
                        {message.model}
                      </Badge>
                    )}
                    {message.disclaimer && (
                      <p className="text-[10px] leading-relaxed text-muted-foreground mt-1 w-full">
                        {message.disclaimer}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="w-8 h-8 rounded bg-secondary/20 flex items-center justify-center border border-secondary/50 shrink-0 mr-3">
                <Loader className="h-4 w-4 text-secondary animate-spin" />
              </div>
              <div className="bg-muted text-foreground border border-border px-4 py-3 rounded-xl rounded-bl-none">
                <p className="text-sm">جاري المعالجة...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-start">
              <div className="bg-destructive/10 text-destructive border border-destructive/30 px-4 py-3 rounded-xl">
                <p className="text-sm">{error}</p>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Quick Commands */}
      <div className="px-6 py-4 border-t border-border bg-card/50 stagger-card">
        <p className="text-xs text-muted-foreground mb-3 font-medium">الأوامر السريعة:</p>
        <div className="flex flex-wrap gap-2">
          {quickCommands.map((cmd) => (
            <Badge
              key={cmd}
              variant="outline"
              className="bg-muted border-border hover:bg-secondary/20 hover:text-secondary hover:border-secondary/50 cursor-pointer py-1.5 px-3"
              onClick={() => handleQuickCommand(cmd)}
            >
              {cmd}
            </Badge>
          ))}
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-border p-4 bg-card stagger-card">
        <form onSubmit={handleSendMessage} className="max-w-3xl mx-auto">
          <div className="relative flex items-center gap-2">
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-10 w-10 text-muted-foreground hover:text-foreground"
            >
              <Plus className="h-4 w-4" />
            </Button>

            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="اكتب سؤالاً أو أمراً..."
              className="bg-muted border-border flex-1 h-10 rounded-full px-4"
              disabled={loading}
            />

            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-10 w-10 text-muted-foreground hover:text-foreground"
              onClick={() => setIsListening(!isListening)}
            >
              <Mic className={`h-4 w-4 ${isListening ? 'text-secondary' : ''}`} />
            </Button>

            <Button
              type="submit"
              size="icon"
              className="h-10 w-10 bg-secondary hover:bg-secondary/90 text-secondary-foreground rounded-full"
              disabled={loading || !inputValue.trim()}
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </form>
      </div>

      {/* Status Bar — real connection state, not a hardcoded badge */}
      <div className="h-8 bg-background border-t border-border flex items-center justify-between px-6 text-[10px] font-mono text-muted-foreground">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1"><Cpu className="w-3 h-3" /> Expert Mode</span>
          <span className="flex items-center gap-1"><Server className="w-3 h-3" /> Current Project</span>
        </div>
        <div className={`flex items-center gap-1 ${statusTextClass}`}>
          <div className={statusDotClass}></div>
          {statusText}
        </div>
      </div>
    </div>
  );
}
