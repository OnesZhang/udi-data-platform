#!/usr/bin/env python3
"""
MySQL导入模块 - 高性能批量导入器

更新策略：
- 设备主表：UPSERT（有则更新，无则插入）
- 明细表：先删除旧明细，再插入新明细
"""

import mysql.connector
import logging
import time
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class UdiImporter:
    """UDI数据高性能导入器"""
    
    def __init__(self, config):
        """
        初始化导入器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.connection = None
        self.batch_size = 1000  # 批量插入大小
        
        # 准备SQL语句
        self._prepare_sql()
    
    def _prepare_sql(self):
        """准备SQL语句"""
        # 主表插入/更新语句（UPSERT）
        self.insert_device_sql = """
        INSERT INTO udi_devices (
            device_record_key, zxxsdycpbs, cpbsbmtxmc, cpbsfbrq, zxxsdyzsydydsl,
            sydycpbs, bszt, sfyzcbayz, zcbacpbs, sfybtzjbs, btcpbsyzxxsdycpbssfyz,
            btcpbs, cpmctymc, spmc, ggxh, sfwblztlcp, cpms, cphhhbh,
            yflbm, qxlb, flbm, tyshxydm, zczbhhzbapzbh, ylqxzcrbarmc,
            ylqxzcrbarywmc, ybbm, cplb, cgzmraqxgxx, sfbjwycxsy,
            zdcfsycs, sfwwjbz, syqsfxyjxmj, mjfs, qtxxdwzlj, tsrq,
            scbssfbhph, scbssfbhxlh, scbssfbhscrq, scbssfbhsxrq,
            tscchcztj, tsccsm, version_number, version_time, version_status,
            correction_number, correction_remark, correction_time,
            has_packing_list, has_storage_list, has_clinical_list
        ) VALUES (
            %(deviceRecordKey)s, %(zxxsdycpbs)s, %(cpbsbmtxmc)s, %(cpbsfbrq)s, %(zxxsdyzsydydsl)s,
            %(sydycpbs)s, %(bszt)s, %(sfyzcbayz)s, %(zcbacpbs)s, %(sfybtzjbs)s, %(btcpbsyzxxsdycpbssfyz)s,
            %(btcpbs)s, %(cpmctymc)s, %(spmc)s, %(ggxh)s, %(sfwblztlcp)s, %(cpms)s, %(cphhhbh)s,
            %(yflbm)s, %(qxlb)s, %(flbm)s, %(tyshxydm)s, %(zczbhhzbapzbh)s, %(ylqxzcrbarmc)s,
            %(ylqxzcrbarywmc)s, %(ybbm)s, %(cplb)s, %(cgzmraqxgxx)s, %(sfbjwycxsy)s,
            %(zdcfsycs)s, %(sfwwjbz)s, %(syqsfxyjxmj)s, %(mjfs)s, %(qtxxdwzlj)s, %(tsrq)s,
            %(scbssfbhph)s, %(scbssfbhxlh)s, %(scbssfbhscrq)s, %(scbssfbhsxrq)s,
            %(tscchcztj)s, %(tsccsm)s, %(versionNumber)s, %(versionTime)s, %(versionStatus)s,
            %(correctionNumber)s, %(correctionRemark)s, %(correctionTime)s,
            %(has_packing_list)s, %(has_storage_list)s, %(has_clinical_list)s
        ) ON DUPLICATE KEY UPDATE
            zxxsdycpbs = VALUES(zxxsdycpbs),
            cpbsbmtxmc = VALUES(cpbsbmtxmc),
            cpbsfbrq = VALUES(cpbsfbrq),
            zxxsdyzsydydsl = VALUES(zxxsdyzsydydsl),
            sydycpbs = VALUES(sydycpbs),
            bszt = VALUES(bszt),
            sfyzcbayz = VALUES(sfyzcbayz),
            zcbacpbs = VALUES(zcbacpbs),
            sfybtzjbs = VALUES(sfybtzjbs),
            btcpbsyzxxsdycpbssfyz = VALUES(btcpbsyzxxsdycpbssfyz),
            btcpbs = VALUES(btcpbs),
            cpmctymc = VALUES(cpmctymc),
            spmc = VALUES(spmc),
            ggxh = VALUES(ggxh),
            sfwblztlcp = VALUES(sfwblztlcp),
            cpms = VALUES(cpms),
            cphhhbh = VALUES(cphhhbh),
            yflbm = VALUES(yflbm),
            qxlb = VALUES(qxlb),
            flbm = VALUES(flbm),
            tyshxydm = VALUES(tyshxydm),
            zczbhhzbapzbh = VALUES(zczbhhzbapzbh),
            ylqxzcrbarmc = VALUES(ylqxzcrbarmc),
            ylqxzcrbarywmc = VALUES(ylqxzcrbarywmc),
            ybbm = VALUES(ybbm),
            cplb = VALUES(cplb),
            cgzmraqxgxx = VALUES(cgzmraqxgxx),
            sfbjwycxsy = VALUES(sfbjwycxsy),
            zdcfsycs = VALUES(zdcfsycs),
            sfwwjbz = VALUES(sfwwjbz),
            syqsfxyjxmj = VALUES(syqsfxyjxmj),
            mjfs = VALUES(mjfs),
            qtxxdwzlj = VALUES(qtxxdwzlj),
            tsrq = VALUES(tsrq),
            scbssfbhph = VALUES(scbssfbhph),
            scbssfbhxlh = VALUES(scbssfbhxlh),
            scbssfbhscrq = VALUES(scbssfbhscrq),
            scbssfbhsxrq = VALUES(scbssfbhsxrq),
            tscchcztj = VALUES(tscchcztj),
            tsccsm = VALUES(tsccsm),
            version_number = VALUES(version_number),
            version_time = VALUES(version_time),
            version_status = VALUES(version_status),
            correction_number = VALUES(correction_number),
            correction_remark = VALUES(correction_remark),
            correction_time = VALUES(correction_time),
            has_packing_list = VALUES(has_packing_list),
            has_storage_list = VALUES(has_storage_list),
            has_clinical_list = VALUES(has_clinical_list)
        """
        
        # 删除明细表旧数据的SQL
        self.delete_packing_sql = "DELETE FROM udi_packing_list WHERE device_record_key = %s"
        self.delete_storage_sql = "DELETE FROM udi_storage_list WHERE device_record_key = %s"
        self.delete_clinical_sql = "DELETE FROM udi_clinical_list WHERE device_record_key = %s"
        self.delete_contact_sql = "DELETE FROM udi_contacts WHERE device_record_key = %s"
        
        # 联系人表插入语句
        self.insert_contact_sql = """
        INSERT INTO udi_contacts (
            device_record_key, qylxrcz, qylxryx, qylxrdh
        ) VALUES (
            %(deviceRecordKey)s, %(qylxrcz)s, %(qylxryx)s, %(qylxrdh)s
        )
        """
        
        # 包装列表表插入语句
        self.insert_packing_sql = """
        INSERT INTO udi_packing_list (
            device_record_key, bzcpbs, cpbzjb, bznhxyjcpbssl, bznhxyjbzcpbs
        ) VALUES (
            %(device_record_key)s, %(bzcpbs)s, %(cpbzjb)s, %(bznhxyjcpbssl)s, %(bznhxyjbzcpbs)s
        )
        """
        
        # 储存条件表插入语句
        self.insert_storage_sql = """
        INSERT INTO udi_storage_list (
            device_record_key, cchcztj, zdz, zgz, jldw
        ) VALUES (
            %(device_record_key)s, %(cchcztj)s, %(zdz)s, %(zgz)s, %(jldw)s
        )
        """
        
        # 临床尺寸表插入语句
        self.insert_clinical_sql = """
        INSERT INTO udi_clinical_list (
            device_record_key, lcsycclx, ccz, ccdw
        ) VALUES (
            %(device_record_key)s, %(lcsycclx)s, %(ccz)s, %(ccdw)s
        )
        """
    
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.connection = mysql.connector.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password,
                autocommit=False
            )
            logger.info("数据库连接成功")
            return True
        except mysql.connector.Error as e:
            logger.error(f"数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("数据库连接已关闭")
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        try:
            yield self.connection
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"事务回滚: {e}")
            raise
    
    def _prepare_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """准备记录数据"""
        prepared = record.copy()
        
        # 处理日期字段
        date_fields = ['cpbsfbrq', 'versionTime', 'correctionTime', 'tsrq']
        for field in date_fields:
            if prepared.get(field):
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(prepared[field], '%Y-%m-%d')
                    prepared[field] = date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    prepared[field] = None
        
        # 处理整数字段
        int_fields = ['zxxsdyzsydydsl', 'versionNumber', 'correctionNumber', 'bznhxyjcpbssl']
        for field in int_fields:
            if prepared.get(field):
                try:
                    prepared[field] = int(prepared[field])
                except ValueError:
                    prepared[field] = None
        
        # 处理嵌套数据
        packing_list = prepared.pop('packing_list', [])
        prepared['has_packing_list'] = prepared.get('has_packing_list', False)
        
        storage_list = prepared.pop('storage_list', [])
        prepared['has_storage_list'] = prepared.get('has_storage_list', False)
        
        clinical_list = prepared.pop('clinical_list', [])
        prepared['has_clinical_list'] = prepared.get('has_clinical_list', False)
        
        # 联系人列表
        contact_list = prepared.pop('contact_list', [])
        if contact_list:
            contact = contact_list[0] if contact_list else {}
            prepared.update({
                'qylxrcz': contact.get('qylxrcz'),
                'qylxryx': contact.get('qylxryx'),
                'qylxrdh': contact.get('qylxrdh')
            })
        
        # 保存嵌套数据
        prepared['_packing_list'] = packing_list
        prepared['_storage_list'] = storage_list
        prepared['_clinical_list'] = clinical_list
        
        return prepared
    
    def _update_record(self, cursor, record: Dict[str, Any]):
        """
        更新单条记录（删除旧明细+插入新明细）
        
        Args:
            cursor: 数据库游标
            record: 记录数据
        """
        prepared = self._prepare_record(record)
        device_key = prepared.get('deviceRecordKey')
        
        if not device_key:
            return
        
        # 1. 插入/更新设备主表（UPSERT）
        cursor.execute(self.insert_device_sql, prepared)
        
        # 2. 删除旧的明细数据
        cursor.execute(self.delete_contact_sql, (device_key,))
        cursor.execute(self.delete_packing_sql, (device_key,))
        cursor.execute(self.delete_storage_sql, (device_key,))
        cursor.execute(self.delete_clinical_sql, (device_key,))
        
        # 3. 插入新的联系人数据
        contact_record = {
            'deviceRecordKey': device_key,
            'qylxrcz': prepared.get('qylxrcz'),
            'qylxryx': prepared.get('qylxryx'),
            'qylxrdh': prepared.get('qylxrdh')
        }
        cursor.execute(self.insert_contact_sql, contact_record)
        
        # 4. 插入新的包装列表数据
        for packing in prepared.get('_packing_list', []):
            packing_record = {
                'device_record_key': device_key,
                'bzcpbs': packing.get('bzcpbs'),
                'cpbzjb': packing.get('cpbzjb'),
                'bznhxyjcpbssl': packing.get('bznhxyjcpbssl'),
                'bznhxyjbzcpbs': packing.get('bznhxyjbzcpbs')
            }
            cursor.execute(self.insert_packing_sql, packing_record)
        
        # 5. 插入新的储存条件数据
        for storage in prepared.get('_storage_list', []):
            storage_record = {
                'device_record_key': device_key,
                'cchcztj': storage.get('cchcztj'),
                'zdz': storage.get('zdz'),
                'zgz': storage.get('zgz'),
                'jldw': storage.get('jldw')
            }
            cursor.execute(self.insert_storage_sql, storage_record)
        
        # 6. 插入新的临床尺寸数据
        for clinical in prepared.get('_clinical_list', []):
            clinical_record = {
                'device_record_key': device_key,
                'lcsycclx': clinical.get('lcsycclx'),
                'ccz': clinical.get('ccz'),
                'ccdw': clinical.get('ccdw')
            }
            cursor.execute(self.insert_clinical_sql, clinical_record)
    
    def _batch_update(self, records: List[Dict[str, Any]]) -> tuple:
        """
        批量更新记录
        
        Args:
            records: 记录列表
            
        Returns:
            (成功数, 失败数)
        """
        if not records:
            return 0, 0
        
        success_count = 0
        fail_count = 0
        
        try:
            cursor = self.connection.cursor()
            
            for record in records:
                try:
                    self._update_record(cursor, record)
                    success_count += 1
                except Exception as e:
                    logger.error(f"更新记录失败: {e}")
                    fail_count += 1
            
            cursor.close()
            
        except mysql.connector.Error as e:
            logger.error(f"批量更新失败: {e}")
            fail_count = len(records)
            success_count = 0
        
        return success_count, fail_count
    
    def import_from_generator(self, record_generator) -> Dict[str, Any]:
        """从生成器导入数据"""
        if not self.connect():
            return {'status': 'failed', 'error': '数据库连接失败'}
        
        start_time = time.time()
        total_records = 0
        success_records = 0
        failed_records = 0
        batch_records = []
        
        logger.info("开始批量导入数据...")
        
        try:
            with self.transaction():
                for record in record_generator:
                    total_records += 1
                    batch_records.append(record)
                    
                    if len(batch_records) >= self.batch_size:
                        success, fail = self._batch_update(batch_records)
                        success_records += success
                        failed_records += fail
                        batch_records = []
                        
                        if total_records % 10000 == 0:
                            logger.info(f"已处理 {total_records} 条记录，成功: {success_records}，失败: {failed_records}")
                
                if batch_records:
                    success, fail = self._batch_update(batch_records)
                    success_records += success
                    failed_records += fail
            
            duration = time.time() - start_time
            
            self._log_import(
                file_name="UDID_FULL_RELEASE_20260801.zip",
                total_records=total_records,
                success_records=success_records,
                failed_records=failed_records,
                status='completed',
                duration=duration
            )
            
            result = {
                'status': 'completed',
                'total_records': total_records,
                'success_records': success_records,
                'failed_records': failed_records,
                'duration_seconds': round(duration, 2),
                'records_per_second': round(total_records / duration, 2) if duration > 0 else 0
            }
            
            logger.info(f"导入完成: {result}")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            self._log_import(
                file_name="UDID_FULL_RELEASE_20260801.zip",
                total_records=total_records,
                success_records=success_records,
                failed_records=failed_records,
                status='failed',
                error=str(e),
                duration=duration
            )
            
            return {
                'status': 'failed',
                'error': str(e),
                'total_records': total_records,
                'success_records': success_records,
                'failed_records': failed_records,
                'duration_seconds': round(duration, 2)
            }
        
        finally:
            self.disconnect()
    
    def _log_import(self, file_name: str, total_records: int, success_records: int, 
                   failed_records: int, status: str, error: str = None, duration: float = 0):
        """记录导入日志"""
        try:
            cursor = self.connection.cursor()
            sql = """
            INSERT INTO import_logs (
                file_name, total_records, success_records, failed_records, 
                status, error_message, duration_seconds
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(sql, (
                file_name, total_records, success_records, failed_records,
                status, error, int(duration)
            ))
            cursor.close()
        except Exception as e:
            logger.warning(f"记录导入日志失败: {e}")

    def test_connection(self) -> bool:
        """测试数据库连接"""
        logger.info("=" * 50)
        logger.info("数据库连接测试")
        logger.info("=" * 50)
        
        db_config = {
            'host': self.config.db_host,
            'port': self.config.db_port,
            'database': self.config.db_name,
            'user': self.config.db_user,
            'password': self.config.db_password
        }
        
        safe_config = db_config.copy()
        if safe_config.get('password'):
            safe_config['password'] = '***' + safe_config['password'][-3:] if len(safe_config['password']) > 3 else '***'
        
        logger.info(f"连接信息: {safe_config}")
        
        try:
            connection = mysql.connector.connect(**db_config)
            
            if connection.is_connected():
                db_info = connection.get_server_info()
                cursor = connection.cursor()
                cursor.execute("SELECT DATABASE();")
                record = cursor.fetchone()
                
                logger.info("✅ 数据库连接成功!")
                logger.info(f"MySQL服务器版本: {db_info}")
                logger.info(f"当前连接数据库: {record[0]}")
                
                cursor.execute("SELECT VERSION();")
                version = cursor.fetchone()
                logger.info(f"数据库版本: {version[0]}")
                
                cursor.execute("SELECT USER();")
                user = cursor.fetchone()
                logger.info(f"当前用户: {user[0]}")
                
                cursor.close()
                connection.close()
                return True
                
        except mysql.connector.Error as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            logger.error("请检查:")
            logger.error("1. 远程MySQL服务器是否可达")
            logger.error("2. 用户名和密码是否正确")
            logger.error("3. 数据库是否存在")
            logger.error("4. 网络连接是否正常")
            return False
        
        logger.info("=" * 50)
        return False
