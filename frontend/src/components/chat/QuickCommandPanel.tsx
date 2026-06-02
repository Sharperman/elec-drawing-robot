/**
 * QuickCommandPanel - 快捷指令面板
 * 输入 "/" 时弹出，提供常用指令快速选择
 */
import React from 'react';

export interface QuickCommand {
  command: string;
  description: string;
  icon: string;
}

const COMMANDS: QuickCommand[] = [
  { command: '/draw', description: '绘制电气图纸或元件', icon: '⚡' },
  { command: '/insert', description: '在指定位置插入元件', icon: '🔌' },
  { command: '/query', description: '查询当前图纸信息', icon: '🔍' },
  { command: '/clear', description: '清除当前图纸内容', icon: '🗑️' },
  { command: '/export', description: '导出图纸文件', icon: '📤' },
];

interface QuickCommandPanelProps {
  onSelect: (command: string) => void;
  filter?: string;
  className?: string;
  onClose?: () => void;
}

const QuickCommandPanel: React.FC<QuickCommandPanelProps> = ({
  onSelect,
  filter = '',
  className,
}) => {
  const filtered = filter
    ? COMMANDS.filter(
        (c) =>
          c.command.includes(filter.toLowerCase()) ||
          c.description.includes(filter)
      )
    : COMMANDS;

  if (filtered.length === 0) return null;

  return (
    <div className={`command-panel ${className ?? ''}`}>
      <div className="command-panel-header">快捷指令</div>
      {filtered.map((cmd) => (
        <button
          key={cmd.command}
          onClick={() => onSelect(cmd.command + ' ')}
          className="command-item"
          type="button"
        >
          <div className="command-item-icon bg-gray-800">
            <span>{cmd.icon}</span>
          </div>
          <div className="min-w-0">
            <div className="text-sm text-gray-200 font-medium">{cmd.command}</div>
            <div className="text-xs text-gray-500 truncate">{cmd.description}</div>
          </div>
        </button>
      ))}
    </div>
  );
};

export { COMMANDS };
export default QuickCommandPanel;
