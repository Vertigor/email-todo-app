"""
数据库操作模块
使用SQLite存储待办事项和已处理邮件记录
"""
import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path
from .models import TodoItem


class Database:
    def __init__(self, db_path: str = "todos.db"):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 待办事项表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                created_at TEXT NOT NULL,
                source_email_id TEXT,
                source_email_subject TEXT,
                completed INTEGER DEFAULT 0,
                completed_at TEXT,
                deleted INTEGER DEFAULT 0,
                deleted_at TEXT
            )
        """)
        
        # 添加 deleted 字段（如果表已存在但没有该字段）
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN deleted INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN deleted_at TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        # 添加 source_email_from 字段
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN source_email_from TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        # 添加 source_email_date 字段
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN source_email_date TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        # 添加 source_email_body 字段
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN source_email_body TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        # 添加 source_email_to 字段（收件人）
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN source_email_to TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        # 添加 source_email_cc 字段（抄送）
        try:
            cursor.execute("ALTER TABLE todos ADD COLUMN source_email_cc TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在

        # 已处理邮件表（避免重复处理）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                email_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
        """)

        # 转发规则表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forward_rules (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                recipients TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_matched_at TEXT,
                match_count INTEGER DEFAULT 0
            )
        """)
        # 0 = 命中后视为已委派/已知会，不再走 LLM 生成自处理待办
        # 1 = 命中后仍生成自处理待办（适用于"抄送知会，自己也要跟进"）
        try:
            cursor.execute("ALTER TABLE forward_rules ADD COLUMN also_create_todo INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        # 已转发邮件记录表（避免重复转发 + 知会流展示）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forwarded_emails (
                email_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                forwarded_at TEXT NOT NULL,
                recipients TEXT NOT NULL,
                PRIMARY KEY (email_id, rule_id)
            )
        """)
        # 快照字段：转发时把原邮件元信息冻结进来，用于"已转发"列表展示，
        # 不依赖 todos 表（命中"不生成待办"的规则时 todos 里没有对应记录）。
        for col_sql in [
            "ALTER TABLE forwarded_emails ADD COLUMN subject TEXT",
            "ALTER TABLE forwarded_emails ADD COLUMN from_addr TEXT",
            "ALTER TABLE forwarded_emails ADD COLUMN original_date TEXT",
            "ALTER TABLE forwarded_emails ADD COLUMN body_preview TEXT",
            "ALTER TABLE forwarded_emails ADD COLUMN rule_description TEXT",
            "ALTER TABLE forwarded_emails ADD COLUMN reason TEXT",
            "ALTER TABLE forwarded_emails ADD COLUMN read INTEGER DEFAULT 0",
            "ALTER TABLE forwarded_emails ADD COLUMN read_at TEXT",
        ]:
            try:
                cursor.execute(col_sql)
            except sqlite3.OperationalError:
                pass

        conn.commit()
        conn.close()

    def add_todo(self, todo: TodoItem) -> bool:
        """
        添加待办事项
        
        Args:
            todo: 待办事项对象
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO todos 
                (id, title, description, due_date, created_at, source_email_id, 
                 source_email_subject, completed, completed_at, deleted, deleted_at, 
                 source_email_from, source_email_to, source_email_cc, source_email_date, source_email_body)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                todo.id,
                todo.title,
                todo.description,
                todo.due_date.isoformat() if todo.due_date else None,
                todo.created_at.isoformat(),
                todo.source_email_id,
                todo.source_email_subject,
                1 if todo.completed else 0,
                todo.completed_at.isoformat() if todo.completed_at else None,
                1 if todo.deleted else 0,
                todo.deleted_at.isoformat() if todo.deleted_at else None,
                todo.source_email_from,
                todo.source_email_to,
                todo.source_email_cc,
                todo.source_email_date.isoformat() if todo.source_email_date else None,
                todo.source_email_body,
            ))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding todo: {e}")
            return False
        finally:
            conn.close()

    def get_todos(self, completed: Optional[bool] = None, deleted: bool = False) -> List[TodoItem]:
        """
        获取待办列表
        
        Args:
            completed: 是否完成，None表示全部
            deleted: 是否获取已删除的（默认False，获取未删除的）
            
        Returns:
            待办事项列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        deleted_filter = "deleted = 1" if deleted else "(deleted = 0 OR deleted IS NULL)"

        if deleted:
            # 回收站：按删除时间降序
            cursor.execute(
                f"SELECT * FROM todos WHERE {deleted_filter} ORDER BY deleted_at DESC"
            )
        elif completed is None:
            # 所有待办：未完成的按截止日期升序，已完成的按完成时间降序
            cursor.execute(
                f"SELECT * FROM todos WHERE {deleted_filter} ORDER BY completed ASC, created_at DESC"
            )
        elif completed:
            # 已完成：按完成时间降序（最近完成的在前）
            cursor.execute(
                f"SELECT * FROM todos WHERE {deleted_filter} AND completed = 1 ORDER BY completed_at DESC"
            )
        else:
            # 未完成：按截止日期升序（越早截止的越前），无截止日期的放最后
            cursor.execute(
                f"""SELECT * FROM todos WHERE {deleted_filter} AND completed = 0 
                   ORDER BY 
                       CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                       due_date ASC,
                       created_at ASC"""
            )

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_todo(row) for row in rows]
    
    def _row_to_todo(self, row) -> TodoItem:
        """将数据库行转换为TodoItem对象"""
        # 获取新增字段，兼容旧数据
        def safe_get(key):
            try:
                return row[key]
            except (IndexError, KeyError):
                return None
        
        source_email_date_str = safe_get('source_email_date')
        
        return TodoItem(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            due_date=datetime.fromisoformat(row['due_date']) if row['due_date'] else None,
            created_at=datetime.fromisoformat(row['created_at']),
            source_email_id=row['source_email_id'],
            source_email_subject=row['source_email_subject'],
            source_email_from=safe_get('source_email_from'),
            source_email_to=safe_get('source_email_to'),
            source_email_cc=safe_get('source_email_cc'),
            source_email_date=datetime.fromisoformat(source_email_date_str) if source_email_date_str else None,
            source_email_body=safe_get('source_email_body'),
            completed=bool(row['completed']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            deleted=bool(row['deleted']) if row['deleted'] is not None else False,
            deleted_at=datetime.fromisoformat(row['deleted_at']) if row['deleted_at'] else None
        )

    def get_todos_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[TodoItem]:
        """
        获取指定日期范围内的待办事项（用于日历视图，排除已删除）
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            待办事项列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 查询所有任务（包括已完成的，排除已删除的），只比较日期部分
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        cursor.execute("""
            SELECT * FROM todos 
            WHERE due_date IS NOT NULL 
            AND (deleted = 0 OR deleted IS NULL)
            AND substr(due_date, 1, 10) >= ? 
            AND substr(due_date, 1, 10) <= ?
            ORDER BY completed ASC, due_date ASC
        """, (start_str, end_str))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_todo(row) for row in rows]

    def mark_email_processed(self, email_id: str):
        """
        标记邮件已处理
        
        Args:
            email_id: 邮件ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO processed_emails VALUES (?, ?)",
                (email_id, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()

    def is_email_processed(self, email_id: str) -> bool:
        """
        检查邮件是否已处理
        
        Args:
            email_id: 邮件ID
            
        Returns:
            是否已处理
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM processed_emails WHERE email_id = ?",
            (email_id,)
        )
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def update_todo_completed(self, todo_id: str, completed: bool) -> bool:
        """
        更新待办完成状态
        
        Args:
            todo_id: 待办ID
            completed: 是否完成
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            completed_at = datetime.now().isoformat() if completed else None
            cursor.execute("""
                UPDATE todos 
                SET completed = ?, completed_at = ?
                WHERE id = ?
            """, (
                1 if completed else 0,
                completed_at,
                todo_id
            ))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating todo: {e}")
            return False
        finally:
            conn.close()

    def get_todo_by_id(self, todo_id: str) -> Optional[TodoItem]:
        """
        根据ID获取待办事项
        
        Args:
            todo_id: 待办ID
            
        Returns:
            待办事项对象，不存在返回None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM todos WHERE id = ?", (todo_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return self._row_to_todo(row)
    
    def soft_delete_todo(self, todo_id: str) -> bool:
        """
        软删除待办事项
        
        Args:
            todo_id: 待办ID
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE todos 
                SET deleted = 1, deleted_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), todo_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error soft deleting todo: {e}")
            return False
        finally:
            conn.close()
    
    def restore_todo(self, todo_id: str) -> bool:
        """
        恢复已删除的待办事项
        
        Args:
            todo_id: 待办ID
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE todos 
                SET deleted = 0, deleted_at = NULL
                WHERE id = ?
            """, (todo_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error restoring todo: {e}")
            return False
        finally:
            conn.close()
    
    def update_todo(self, todo_id: str, title: str = None, description: str = None, 
                    completed: bool = None, due_date = ..., clear_due_date: bool = False) -> bool:
        """
        更新待办事项
        
        Args:
            todo_id: 待办ID
            title: 新标题（可选）
            description: 新描述（可选）
            completed: 新完成状态（可选）
            due_date: 新截止日期（可选，使用 ... 表示不更新）
            clear_due_date: 是否清除截止日期
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if completed is not None:
                updates.append("completed = ?")
                params.append(1 if completed else 0)
                if completed:
                    updates.append("completed_at = ?")
                    params.append(datetime.now().isoformat())
                else:
                    updates.append("completed_at = NULL")
            
            # 处理截止日期：clear_due_date=True 清除，due_date有值则更新
            if clear_due_date:
                updates.append("due_date = NULL")
            elif due_date is not ... and due_date is not None:
                updates.append("due_date = ?")
                params.append(due_date.isoformat())
            
            if not updates:
                return True  # 没有要更新的字段
            
            params.append(todo_id)
            sql = f"UPDATE todos SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating todo: {e}")
            return False
        finally:
            conn.close()

    # ==================== 转发规则操作 ====================

    def add_forward_rule(self, rule_id: str, description: str, recipients: list, enabled: bool = True, also_create_todo: bool = False) -> bool:
        """添加转发规则"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO forward_rules (id, description, recipients, enabled, created_at, also_create_todo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rule_id, description, json.dumps(recipients, ensure_ascii=False), 1 if enabled else 0, datetime.now().isoformat(), 1 if also_create_todo else 0)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding forward rule: {e}")
            return False
        finally:
            conn.close()

    def get_forward_rules(self, enabled_only: bool = False) -> list:
        """获取转发规则列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            if enabled_only:
                cursor.execute("SELECT * FROM forward_rules WHERE enabled = 1 ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM forward_rules ORDER BY created_at DESC")
            rows = cursor.fetchall()
            rules = []
            for row in rows:
                rules.append({
                    "id": row['id'],
                    "description": row['description'],
                    "recipients": json.loads(row['recipients']),
                    "enabled": bool(row['enabled']),
                    "created_at": row['created_at'],
                    "last_matched_at": row['last_matched_at'],
                    "match_count": row['match_count'] or 0,
                    "also_create_todo": bool(row['also_create_todo']) if 'also_create_todo' in row.keys() else False
                })
            return rules
        finally:
            conn.close()

    def get_forward_rule(self, rule_id: str) -> dict:
        """获取单个转发规则"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM forward_rules WHERE id = ?", (rule_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row['id'],
                    "description": row['description'],
                    "recipients": json.loads(row['recipients']),
                    "enabled": bool(row['enabled']),
                    "created_at": row['created_at'],
                    "last_matched_at": row['last_matched_at'],
                    "match_count": row['match_count'] or 0,
                    "also_create_todo": bool(row['also_create_todo']) if 'also_create_todo' in row.keys() else False
                }
            return None
        finally:
            conn.close()

    def update_forward_rule(self, rule_id: str, description: str = None, recipients: list = None, enabled: bool = None, also_create_todo: bool = None) -> bool:
        """更新转发规则"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            updates = []
            params = []
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if recipients is not None:
                updates.append("recipients = ?")
                params.append(json.dumps(recipients, ensure_ascii=False))
            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)
            if also_create_todo is not None:
                updates.append("also_create_todo = ?")
                params.append(1 if also_create_todo else 0)
            if not updates:
                return True
            params.append(rule_id)
            sql = f"UPDATE forward_rules SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating forward rule: {e}")
            return False
        finally:
            conn.close()

    def delete_forward_rule(self, rule_id: str) -> bool:
        """删除转发规则"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM forward_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting forward rule: {e}")
            return False
        finally:
            conn.close()

    def update_forward_rule_match(self, rule_id: str) -> bool:
        """更新转发规则的匹配信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE forward_rules 
                SET last_matched_at = ?, match_count = match_count + 1
                WHERE id = ?
            """, (datetime.now().isoformat(), rule_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating forward rule match: {e}")
            return False
        finally:
            conn.close()

    def is_email_forwarded(self, email_id: str, rule_id: str) -> bool:
        """检查邮件是否已被某规则转发过"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM forwarded_emails WHERE email_id = ? AND rule_id = ?",
                (email_id, rule_id)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def mark_email_forwarded(
        self,
        email_id: str,
        rule_id: str,
        recipients: list,
        subject: str = "",
        from_addr: str = "",
        original_date: str = "",
        body_preview: str = "",
        rule_description: str = "",
        reason: str = ""
    ) -> bool:
        """记录邮件已转发（含快照，用于"已转发"列表展示）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO forwarded_emails
                (email_id, rule_id, forwarded_at, recipients,
                 subject, from_addr, original_date, body_preview,
                 rule_description, reason, read, read_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    email_id, rule_id, datetime.now().isoformat(),
                    json.dumps(recipients, ensure_ascii=False),
                    subject, from_addr, original_date,
                    (body_preview or "")[:500],
                    rule_description, reason
                )
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking email forwarded: {e}")
            return False
        finally:
            conn.close()

    def get_forwarded_emails(self, only_unread: bool = False, limit: int = 200) -> list:
        """获取已转发邮件列表（用于「已转发」Tab 展示）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = "SELECT * FROM forwarded_emails"
            if only_unread:
                sql += " WHERE (read = 0 OR read IS NULL)"
            sql += " ORDER BY forwarded_at DESC LIMIT ?"
            cursor.execute(sql, (limit,))
            rows = cursor.fetchall()
            keys = set(rows[0].keys()) if rows else set()
            items = []
            for row in rows:
                items.append({
                    "email_id": row["email_id"],
                    "rule_id": row["rule_id"],
                    "forwarded_at": row["forwarded_at"],
                    "recipients": json.loads(row["recipients"]) if row["recipients"] else [],
                    "subject": row["subject"] if "subject" in keys else "",
                    "from_addr": row["from_addr"] if "from_addr" in keys else "",
                    "original_date": row["original_date"] if "original_date" in keys else "",
                    "body_preview": row["body_preview"] if "body_preview" in keys else "",
                    "rule_description": row["rule_description"] if "rule_description" in keys else "",
                    "reason": row["reason"] if "reason" in keys else "",
                    "read": bool(row["read"]) if "read" in keys and row["read"] is not None else False,
                    "read_at": row["read_at"] if "read_at" in keys else None,
                })
            return items
        finally:
            conn.close()

    def get_unread_forwarded_count(self) -> int:
        """获取未读已转发邮件数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM forwarded_emails WHERE read = 0 OR read IS NULL")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0
        finally:
            conn.close()

    def mark_forwarded_read(self, email_id: str, rule_id: str, read: bool = True) -> bool:
        """标记单条已转发记录为已读/未读"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE forwarded_emails SET read = ?, read_at = ? WHERE email_id = ? AND rule_id = ?",
                (1 if read else 0, datetime.now().isoformat() if read else None, email_id, rule_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def mark_all_forwarded_read(self) -> int:
        """全部标为已读，返回受影响行数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE forwarded_emails SET read = 1, read_at = ? WHERE read = 0 OR read IS NULL",
                (datetime.now().isoformat(),)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def clear_all_data(self):
        """
        清空所有数据（待办事项和已处理邮件记录）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM todos")
        cursor.execute("DELETE FROM processed_emails")
        cursor.execute("DELETE FROM forwarded_emails")
        
        conn.commit()
        conn.close()
