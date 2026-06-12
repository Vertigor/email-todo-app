"""
Todo API 路由
"""
from typing import Optional
from datetime import datetime
from calendar import monthrange

from fastapi import APIRouter, HTTPException

from deploy_starter.database import Database
from deploy_starter.schemas import CompleteTodoRequest, UpdateTodoRequest
from deploy_starter.utils import get_db_path

router = APIRouter(prefix="/api/todos", tags=["todos"])
db = Database(get_db_path())


@router.get("")
async def get_todos(completed: Optional[bool] = None):
    """获取待办列表（不包含已删除）"""
    todos = db.get_todos(completed, deleted=False)
    return {"todos": [todo.dict() for todo in todos]}


@router.get("/deleted")
async def get_deleted_todos():
    """获取已删除的待办列表（回收站）"""
    todos = db.get_todos(deleted=True)
    return {"todos": [todo.dict() for todo in todos]}


@router.get("/calendar")
async def get_todos_calendar(year: int, month: int):
    """获取日历视图的待办事项"""
    # 计算月份的第一天和最后一天
    _, last_day = monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, last_day, 23, 59, 59)
    
    todos = db.get_todos_by_date_range(start_date, end_date)
    
    # 按日期分组
    calendar = {}
    for todo in todos:
        if todo.due_date:
            date_key = todo.due_date.strftime("%Y-%m-%d")
            if date_key not in calendar:
                calendar[date_key] = []
            calendar[date_key].append(todo.dict())
    
    return {"calendar": calendar}


@router.get("/{todo_id}")
async def get_todo(todo_id: str):
    """获取单个待办详情"""
    todo = db.get_todo_by_id(todo_id)
    if todo:
        return {"todo": todo.dict()}
    else:
        raise HTTPException(status_code=404, detail="待办事项不存在")


@router.put("/{todo_id}")
async def update_todo(todo_id: str, request: UpdateTodoRequest):
    """更新待办事项"""
    # 检查待办是否存在
    todo = db.get_todo_by_id(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    
    # 解析截止日期
    due_date = None
    clear_due_date = False
    
    # 检查 request.due_date：空字符串表示清除，有值则解析
    if request.due_date is not None:
        if request.due_date == "":
            clear_due_date = True
        else:
            try:
                due_date = datetime.fromisoformat(request.due_date.replace("Z", "+00:00"))
                if due_date.tzinfo:
                    due_date = due_date.replace(tzinfo=None)
            except:
                pass
    
    success = db.update_todo(
        todo_id,
        title=request.title,
        description=request.description,
        completed=request.completed,
        due_date=due_date,
        clear_due_date=clear_due_date
    )
    
    if success:
        return {"success": True, "message": "更新成功"}
    else:
        raise HTTPException(status_code=500, detail="更新失败")


@router.put("/{todo_id}/complete")
async def complete_todo(todo_id: str, request: CompleteTodoRequest):
    """标记待办为完成/未完成"""
    success = db.update_todo_completed(todo_id, request.completed)
    if success:
        return {"success": True, "message": "更新成功"}
    else:
        raise HTTPException(status_code=404, detail="待办事项不存在")


@router.put("/{todo_id}/delete")
async def delete_todo(todo_id: str):
    """软删除待办事项（移到回收站）"""
    success = db.soft_delete_todo(todo_id)
    if success:
        return {"success": True, "message": "已移到回收站"}
    else:
        raise HTTPException(status_code=404, detail="待办事项不存在")


@router.put("/{todo_id}/restore")
async def restore_todo(todo_id: str):
    """恢复已删除的待办事项"""
    success = db.restore_todo(todo_id)
    if success:
        return {"success": True, "message": "已恢复"}
    else:
        raise HTTPException(status_code=404, detail="待办事项不存在")
