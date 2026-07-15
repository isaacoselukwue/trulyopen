import { useState } from "react";
import { Check, Copy } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    void navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="group relative overflow-hidden rounded-lg border">
      <div className="flex items-center justify-between border-b bg-muted/50 px-3 py-1">
        <span className="text-xs text-muted-foreground">{language || "code"}</span>
        <Button variant="ghost" size="icon" className="size-7" aria-label="Copy code" onClick={copy}>
          {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
        </Button>
      </div>
      <div className="overflow-x-auto">
        <SyntaxHighlighter
          language={language || "text"}
          style={oneDark}
          customStyle={{ margin: 0, borderRadius: 0, fontSize: "0.825rem", background: "transparent" }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

export function Markdown({ content }: { content: string }) {
  return (
    <div className="space-y-3 text-sm leading-7 [&_a]:underline [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold [&_li]:ml-4 [&_ol]:list-decimal [&_ol]:space-y-1 [&_table]:w-full [&_table]:text-left [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:bg-muted/50 [&_th]:px-2 [&_th]:py-1 [&_ul]:list-disc [&_ul]:space-y-1 [&_blockquote]:border-l-2 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className ?? "");
            const text = String(children).replace(/\n$/, "");
            if (match || text.includes("\n")) {
              return <CodeBlock language={match?.[1] ?? ""} code={text} />;
            }
            return (
              <code
                className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.825em]"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
