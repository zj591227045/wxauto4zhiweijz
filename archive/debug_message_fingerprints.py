#!/usr/bin/env python3
"""
调试消息指纹重复问题
"""

import sqlite3
import hashlib
import os
from collections import Counter

def analyze_message_processor_db():
    """专门分析message_processor.db"""
    db_path = "data/message_processor.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("=== 分析 message_processor.db ===")
            
            # 获取所有消息记录
            cursor.execute('''
                SELECT fingerprint, chat_target, message_id, content, sender, 
                       time_context, sequence_position, status, accounting_status,
                       created_at, updated_at
                FROM message_records 
                ORDER BY created_at DESC
            ''')
            
            records = cursor.fetchall()
            print(f"总记录数: {len(records)}")
            
            # 检查指纹重复
            fingerprints = [r[0] for r in records]
            fingerprint_counts = Counter(fingerprints)
            
            duplicates = {fp: count for fp, count in fingerprint_counts.items() if count > 1}
            
            if duplicates:
                print(f"\n发现 {len(duplicates)} 个重复的指纹:")
                for fp, count in duplicates.items():
                    print(f"\n指纹 {fp} 重复 {count} 次:")
                    
                    # 显示重复记录的详情
                    duplicate_records = [r for r in records if r[0] == fp]
                    for i, record in enumerate(duplicate_records):
                        fingerprint, chat_target, message_id, content, sender, time_context, sequence_position, status, accounting_status, created_at, updated_at = record
                        print(f"  记录 {i+1}:")
                        print(f"    消息ID: {message_id}")
                        print(f"    内容: {content[:50]}...")
                        print(f"    发送者: {sender}")
                        print(f"    时间上下文: {time_context}")
                        print(f"    序列位置: {sequence_position}")
                        print(f"    状态: {status}")
                        print(f"    记账状态: {accounting_status}")
                        print(f"    创建时间: {created_at}")
                        print(f"    更新时间: {updated_at}")
                        print()
            else:
                print("✓ 没有发现重复的指纹")
            
            # 检查内容重复（不同指纹但内容相同）
            print("\n=== 检查内容重复 ===")
            content_counts = Counter([r[3] for r in records])  # content字段
            content_duplicates = {content: count for content, count in content_counts.items() if count > 1}
            
            if content_duplicates:
                print(f"发现 {len(content_duplicates)} 个重复的内容:")
                for content, count in content_duplicates.items():
                    print(f"\n内容 '{content[:30]}...' 重复 {count} 次:")
                    
                    # 显示相同内容的记录
                    same_content_records = [r for r in records if r[3] == content]
                    for i, record in enumerate(same_content_records):
                        fingerprint, chat_target, message_id, content_full, sender, time_context, sequence_position, status, accounting_status, created_at, updated_at = record
                        print(f"  记录 {i+1}: 指纹={fingerprint}, ID={message_id}, 状态={status}, 记账={accounting_status}, 时间={created_at}")
            
            # 检查最新的消息
            print(f"\n=== 最新的20条消息 ===")
            for i, record in enumerate(records[:20]):
                fingerprint, chat_target, message_id, content, sender, time_context, sequence_position, status, accounting_status, created_at, updated_at = record
                print(f"{i+1:2d}. [{chat_target}] {content[:40]}...")
                print(f"     ID={message_id}, 指纹={fingerprint[:8]}..., 状态={status}, 记账={accounting_status}")
                print(f"     创建={created_at}, 更新={updated_at}")
                print()
                    
    except Exception as e:
        print(f"分析失败: {e}")

if __name__ == "__main__":
    analyze_message_processor_db() 