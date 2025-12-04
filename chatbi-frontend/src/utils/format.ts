/**
 * 格式化工具函数
 */

/**
 * 格式化 ISO 时间字符串为友好格式
 * @param isoString ISO 时间字符串 (如 2025-12-01T05:49:23.669795)
 * @returns 格式化后的字符串 (如 2025-12-01 05:49:23)
 */
export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  } catch {
    return isoString;
  }
}

/**
 * 格式化毫秒为秒（保留2位小数）
 * @param ms 毫秒数
 * @returns 格式化后的秒数字符串
 */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '-';
  const seconds = ms / 1000;
  return `${seconds.toFixed(2)}s`;
}

/**
 * 格式化相对时间（如：2小时前）
 * @param isoString ISO 时间字符串
 * @returns 相对时间字符串
 */
export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffSec < 60) return '刚刚';
    if (diffMin < 60) return `${diffMin}分钟前`;
    if (diffHour < 24) return `${diffHour}小时前`;
    if (diffDay < 30) return `${diffDay}天前`;
    
    return formatDateTime(isoString);
  } catch {
    return isoString;
  }
}
