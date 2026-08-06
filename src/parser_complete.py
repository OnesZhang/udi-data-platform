#!/usr/bin/env python3
"""
完整的XML解析器 - 处理所有嵌套字段
"""

import xml.etree.ElementTree as ET
import zipfile
import re
import logging
from typing import Generator, Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class UdiParserComplete:
    """完整的UDI XML解析器"""
    
    def __init__(self):
        """初始化解析器"""
        # 设备主表字段
        self.device_fields = [
            'zxxsdycpbs', 'cpbsbmtxmc', 'cpbsfbrq', 'zxxsdyzsydydsl', 'sydycpbs',
            'bszt', 'sfyzcbayz', 'zcbacpbs', 'sfybtzjbs', 'btcpbsyzxxsdycpbssfyz',
            'btcpbs', 'cpmctymc', 'spmc', 'ggxh', 'sfwblztlcp', 'cpms', 'cphhhbh',
            'yflbm', 'qxlb', 'flbm', 'tyshxydm', 'zczbhhzbapzbh', 'ylqxzcrbarmc',
            'ylqxzcrbarywmc', 'ybbm', 'cplb', 'cgzmraqxgxx', 'sfbjwycxsy',
            'zdcfsycs', 'sfwwjbz', 'syqsfxyjxmj', 'mjfs', 'qtxxdwzlj', 'tsrq',
            'scbssfbhph', 'scbssfbhxlh', 'scbssfbhscrq', 'scbssfbhsxrq',
            'tscchcztj', 'tsccsm', 'deviceRecordKey', 'versionNumber', 'versionTime',
            'versionStauts', 'correctionNumber', 'correctionRemark', 'correctionTime'
        ]
        
        # 包装列表字段
        self.packing_fields = ['bzcpbs', 'cpbzjb', 'bznhxyjcpbssl', 'bznhxyjbzcpbs']
        
        # 储存条件字段
        self.storage_fields = ['cchcztj', 'zdz', 'zgz', 'jldw']
        
        # 临床尺寸字段
        self.clinical_fields = ['lcsycclx', 'ccz', 'ccdw']
        
        # 联系人字段
        self.contact_fields = ['qylxrcz', 'qylxryx', 'qylxrdh']
        
        # 需要清理的无效字符模式
        self.invalid_patterns = [
            r'&#13;',          # 回车符
            r'&#10;',          # 换行符
            r'&#9;',           # 制表符
            r'[\x00-\x08]',   # 控制字符
            r'[\x0B\x0C]',    # 垂直制表符和换页符
            r'[\x0E-\x1F]',   # 其他控制字符
            r'[\x7F-\x9F]',   # 删除字符和扩展控制字符
        ]
    
    def _clean_xml_content(self, content: str) -> str:
        """清理XML内容，移除无效字符"""
        for pattern in self.invalid_patterns:
            content = re.sub(pattern, '', content)
        
        # 修复常见的XML实体问题
        content = content.replace('&', '&amp;')
        content = content.replace('&amp;amp;', '&amp;')
        content = content.replace('&amp;lt;', '&lt;')
        content = content.replace('&amp;gt;', '&gt;')
        content = content.replace('&amp;quot;', '&quot;')
        content = content.replace('&amp;apos;', '&apos;')
        
        return content
    
    def _try_parse_with_cleanup(self, content: str) -> Optional[ET.Element]:
        """尝试解析XML，如果失败则清理后重试"""
        # 第一次尝试：直接解析
        try:
            return ET.fromstring(content)
        except ET.ParseError:
            pass
        
        # 第二次尝试：清理后解析
        try:
            cleaned_content = self._clean_xml_content(content)
            return ET.fromstring(cleaned_content)
        except ET.ParseError:
            pass
        
        # 第三次尝试：使用正则表达式提取设备记录
        logger.warning("使用正则表达式提取设备记录")
        return self._extract_with_regex(content)
    
    def _extract_with_regex(self, content: str) -> Optional[ET.Element]:
        """使用正则表达式提取设备记录"""
        try:
            root = ET.Element('udid')
            devices_elem = ET.SubElement(root, 'devices')
            
            # 提取设备记录
            device_pattern = r'<device>(.*?)</device>'
            devices = re.findall(device_pattern, content, re.DOTALL)
            
            for device_content in devices:
                device_elem = ET.SubElement(devices_elem, 'device')
                
                # 提取设备主表字段
                for field in self.device_fields:
                    field_pattern = f'<{field}>(.*?)</{field}>'
                    match = re.search(field_pattern, device_content, re.DOTALL)
                    if match:
                        field_elem = ET.SubElement(device_elem, field)
                        field_elem.text = match.group(1).strip()
                    else:
                        field_elem = ET.SubElement(device_elem, field)
                        field_elem.text = ''
                
                # 提取包装列表
                packing_pattern = r'<packingList>(.*?)</packingList>'
                packing_match = re.search(packing_pattern, device_content, re.DOTALL)
                if packing_match:
                    packing_list_elem = ET.SubElement(device_elem, 'packingList')
                    packing_pattern_inner = r'<packing>(.*?)</packing>'
                    packings = re.findall(packing_pattern_inner, packing_match.group(1), re.DOTALL)
                    
                    for packing_content in packings:
                        packing_elem = ET.SubElement(packing_list_elem, 'packing')
                        for field in self.packing_fields:
                            field_pattern = f'<{field}>(.*?)</{field}>'
                            match = re.search(field_pattern, packing_content, re.DOTALL)
                            if match:
                                field_elem = ET.SubElement(packing_elem, field)
                                field_elem.text = match.group(1).strip()
                            else:
                                field_elem = ET.SubElement(packing_elem, field)
                                field_elem.text = ''
                
                # 提取储存条件
                storage_pattern = r'<storageList>(.*?)</storageList>'
                storage_match = re.search(storage_pattern, device_content, re.DOTALL)
                if storage_match:
                    storage_list_elem = ET.SubElement(device_elem, 'storageList')
                    storage_pattern_inner = r'<storage>(.*?)</storage>'
                    storages = re.findall(storage_pattern_inner, storage_match.group(1), re.DOTALL)
                    
                    for storage_content in storages:
                        storage_elem = ET.SubElement(storage_list_elem, 'storage')
                        for field in self.storage_fields:
                            field_pattern = f'<{field}>(.*?)</{field}>'
                            match = re.search(field_pattern, storage_content, re.DOTALL)
                            if match:
                                field_elem = ET.SubElement(storage_elem, field)
                                field_elem.text = match.group(1).strip()
                            else:
                                field_elem = ET.SubElement(storage_elem, field)
                                field_elem.text = ''
                
                # 提取临床尺寸
                clinical_pattern = r'<clinicalList>(.*?)</clinicalList>'
                clinical_match = re.search(clinical_pattern, device_content, re.DOTALL)
                if clinical_match:
                    clinical_list_elem = ET.SubElement(device_elem, 'clinicalList')
                    clinical_pattern_inner = r'<clinical>(.*?)</clinical>'
                    clinicals = re.findall(clinical_pattern_inner, clinical_match.group(1), re.DOTALL)
                    
                    for clinical_content in clinicals:
                        clinical_elem = ET.SubElement(clinical_list_elem, 'clinical')
                        for field in self.clinical_fields:
                            field_pattern = f'<{field}>(.*?)</{field}>'
                            match = re.search(field_pattern, clinical_content, re.DOTALL)
                            if match:
                                field_elem = ET.SubElement(clinical_elem, field)
                                field_elem.text = match.group(1).strip()
                            else:
                                field_elem = ET.SubElement(clinical_elem, field)
                                field_elem.text = ''
                
                # 提取联系人信息
                contact_pattern = r'<contactList>(.*?)</contactList>'
                contact_match = re.search(contact_pattern, device_content, re.DOTALL)
                if contact_match:
                    contact_list_elem = ET.SubElement(device_elem, 'contactList')
                    contact_pattern_inner = r'<contact>(.*?)</contact>'
                    contacts = re.findall(contact_pattern_inner, contact_match.group(1), re.DOTALL)
                    
                    for contact_content in contacts:
                        contact_elem = ET.SubElement(contact_list_elem, 'contact')
                        for field in self.contact_fields:
                            field_pattern = f'<{field}>(.*?)</{field}>'
                            match = re.search(field_pattern, contact_content, re.DOTALL)
                            if match:
                                field_elem = ET.SubElement(contact_elem, field)
                                field_elem.text = match.group(1).strip()
                            else:
                                field_elem = ET.SubElement(contact_elem, field)
                                field_elem.text = ''
            
            return root
            
        except Exception as e:
            logger.error(f"正则表达式提取失败: {e}")
            return None
    
    def parse_zip_file(self, zip_path: str) -> Generator[Dict[str, Any], None, None]:
        """解析ZIP文件中的所有XML文件"""
        logger.info(f"开始解析ZIP文件: {zip_path}")
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml')]
            logger.info(f"发现 {len(xml_files)} 个XML文件")
            
            success_count = 0
            error_count = 0
            
            for i, xml_file in enumerate(xml_files, 1):
                logger.info(f"处理文件 {i}/{len(xml_files)}: {xml_file}")
                
                try:
                    with zip_ref.open(xml_file) as f:
                        content = f.read().decode('utf-8')
                        
                        root = self._try_parse_with_cleanup(content)
                        
                        if root is not None:
                            devices = root.findall('.//device')
                            for device in devices:
                                record = self._extract_device_data(device)
                                if record:
                                    yield record
                                    success_count += 1
                        else:
                            logger.warning(f"无法解析文件: {xml_file}")
                            error_count += 1
                            
                except Exception as e:
                    logger.error(f"处理文件失败 {xml_file}: {e}")
                    error_count += 1
            
            logger.info(f"解析完成: 成功 {success_count} 条记录，失败 {error_count} 个文件")
    
    def _extract_device_data(self, device_elem) -> Optional[Dict[str, Any]]:
        """从设备元素提取数据"""
        record = {}
        
        # 提取设备主表字段
        for field in self.device_fields:
            elem = device_elem.find(field)
            if elem is not None and elem.text:
                record[field] = elem.text.strip()
            else:
                record[field] = None
        
        # 提取包装列表
        packing_list = device_elem.find('packingList')
        if packing_list is not None:
            record['packing_list'] = []
            for packing in packing_list.findall('packing'):
                packing_data = {}
                for field in self.packing_fields:
                    elem = packing.find(field)
                    if elem is not None and elem.text:
                        packing_data[field] = elem.text.strip()
                    else:
                        packing_data[field] = None
                record['packing_list'].append(packing_data)
            record['has_packing_list'] = True
        else:
            record['has_packing_list'] = False
        
        # 提取储存条件
        storage_list = device_elem.find('storageList')
        if storage_list is not None:
            record['storage_list'] = []
            for storage in storage_list.findall('storage'):
                storage_data = {}
                for field in self.storage_fields:
                    elem = storage.find(field)
                    if elem is not None and elem.text:
                        storage_data[field] = elem.text.strip()
                    else:
                        storage_data[field] = None
                record['storage_list'].append(storage_data)
            record['has_storage_list'] = True
        else:
            record['has_storage_list'] = False
        
        # 提取临床尺寸
        clinical_list = device_elem.find('clinicalList')
        if clinical_list is not None:
            record['clinical_list'] = []
            for clinical in clinical_list.findall('clinical'):
                clinical_data = {}
                for field in self.clinical_fields:
                    elem = clinical.find(field)
                    if elem is not None and elem.text:
                        clinical_data[field] = elem.text.strip()
                    else:
                        clinical_data[field] = None
                record['clinical_list'].append(clinical_data)
            record['has_clinical_list'] = True
        else:
            record['has_clinical_list'] = False
        
        # 提取联系人信息
        contact_list = device_elem.find('contactList')
        if contact_list is not None:
            record['contact_list'] = []
            for contact in contact_list.findall('contact'):
                contact_data = {}
                for field in self.contact_fields:
                    elem = contact.find(field)
                    if elem is not None and elem.text:
                        contact_data[field] = elem.text.strip()
                    else:
                        contact_data[field] = None
                record['contact_list'].append(contact_data)
        
        # 数据验证
        if not self._validate_record(record):
            return None
            
        return record
    
    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """验证记录数据"""
        # 必须字段检查
        required_fields = ['deviceRecordKey', 'zxxsdycpbs', 'cpbsbmtxmc']
        for field in required_fields:
            if not record.get(field):
                logger.debug(f"缺少必填字段: {field}")
                return False
        
        return True
    
    def test_complete_parsing(self, zip_path: str):
        """测试完整解析功能"""
        print("测试完整解析功能")
        print("=" * 60)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # 读取第一个XML文件
            xml_file = zip_ref.namelist()[0]
            print(f"测试文件: {xml_file}")
            
            with zip_ref.open(xml_file) as f:
                content = f.read().decode('utf-8')
                
                root = self._try_parse_with_cleanup(content)
                
                if root is not None:
                    devices = root.findall('.//device')
                    print(f"✅ 解析成功，提取到 {len(devices)} 条记录")
                    
                    # 统计嵌套字段
                    packing_count = 0
                    storage_count = 0
                    clinical_count = 0
                    
                    for device in devices:
                        if device.find('packingList') is not None:
                            packing_count += 1
                        if device.find('storageList') is not None:
                            storage_count += 1
                        if device.find('clinicalList') is not None:
                            clinical_count += 1
                    
                    print(f"\n嵌套字段统计:")
                    print(f"  包装列表: {packing_count}/{len(devices)} ({packing_count/len(devices)*100:.1f}%)")
                    print(f"  储存条件: {storage_count}/{len(devices)} ({storage_count/len(devices)*100:.1f}%)")
                    print(f"  临床尺寸: {clinical_count}/{len(devices)} ({clinical_count/len(devices)*100:.1f}%)")
                    
                    # 显示第一条记录的详细信息
                    if devices:
                        record = self._extract_device_data(devices[0])
                        if record:
                            print(f"\n第一条记录详情:")
                            print(f"  设备记录键: {record.get('deviceRecordKey')}")
                            print(f"  产品标识: {record.get('zxxsdycpbs')}")
                            print(f"  产品名称: {record.get('cpmctymc')}")
                            print(f"  有包装列表: {record.get('has_packing_list')}")
                            print(f"  有储存条件: {record.get('has_storage_list')}")
                            print(f"  有临床尺寸: {record.get('has_clinical_list')}")
                            
                            if record.get('packing_list'):
                                print(f"  包装列表数量: {len(record['packing_list'])}")
                            if record.get('storage_list'):
                                print(f"  储存条件数量: {len(record['storage_list'])}")
                            if record.get('clinical_list'):
                                print(f"  临床尺寸数量: {len(record['clinical_list'])}")
                else:
                    print("❌ 解析失败")
