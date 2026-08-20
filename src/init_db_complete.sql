-- UDI医疗器械数据平台数据库初始化脚本
-- 数据库由 db_initializer.py 创建并切换，此处仅建表

-- ============================================
-- 1. 设备主表
-- ============================================
CREATE TABLE IF NOT EXISTS udi_devices (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_record_key VARCHAR(100) NOT NULL COMMENT '设备记录键',
    zxxsdycpbs VARCHAR(100) COMMENT '最小销售单元产品标识',
    cpbsbmtxmc VARCHAR(100) COMMENT '医疗器械唯一标识编码体系名称',
    cpbsfbrq DATE COMMENT '产品标识发布日期',
    zxxsdyzsydydsl INT COMMENT '最小销售单元中使用单元的数量',
    sydycpbs VARCHAR(100) COMMENT '使用单元产品标识',
    bszt VARCHAR(50) COMMENT '标识载体',
    sfyzcbayz VARCHAR(10) COMMENT '是否与注册/备案产品标识一致',
    zcbacpbs VARCHAR(100) COMMENT '注册/备案产品标识',
    sfybtzjbs VARCHAR(10) COMMENT '是否有本体标识',
    btcpbsyzxxsdycpbssfyz VARCHAR(10) COMMENT '本体产品标识与最小销售单元产品标识是否一致',
    btcpbs VARCHAR(100) COMMENT '本体产品标识',
    cpmctymc VARCHAR(500) COMMENT '产品名称/通用名称',
    spmc VARCHAR(500) COMMENT '商品名称',
    ggxh VARCHAR(500) COMMENT '规格型号',
    sfwblztlcp VARCHAR(10) COMMENT '是否为包类/组套类产品',
    cpms TEXT COMMENT '产品描述',
    cphhhbh VARCHAR(100) COMMENT '产品货号或编号',
    yflbm VARCHAR(100) COMMENT '分类编码',
    qxlb VARCHAR(50) COMMENT '器械类别',
    flbm VARCHAR(50) COMMENT '分类编码',
    tyshxydm VARCHAR(100) COMMENT '统一社会信用代码',
    zczbhhzbapzbh TEXT COMMENT '注册证号/备案凭证号',
    ylqxzcrbarmc VARCHAR(500) COMMENT '注册人/备案人名称',
    ylqxzcrbarywmc VARCHAR(500) COMMENT '注册人/备案人英文名称',
    ybbm TEXT COMMENT '医保编码',
    cplb VARCHAR(50) COMMENT '产品类别',
    cgzmraqxgxx VARCHAR(500) COMMENT '采购周期风险更新信息',
    sfbjwycxsy VARCHAR(10) COMMENT '是否包含唯一标识信息',
    zdcfsycs VARCHAR(100) COMMENT '最大重复使用次数',
    sfwwjbz VARCHAR(10) COMMENT '是否为无菌包装',
    syqsfxyjxmj VARCHAR(10) COMMENT '使用前是否需要进行灭菌',
    mjfs TEXT COMMENT '灭菌方式',
    qtxxdwzlj TEXT COMMENT '其他信息位置链接',
    tsrq DATE COMMENT '提交日期',
    scbssfbhph VARCHAR(10) COMMENT '生产标识是否包含批次号',
    scbssfbhxlh VARCHAR(10) COMMENT '生产标识是否包含序列号',
    scbssfbhscrq VARCHAR(10) COMMENT '生产标识是否包含生产日期',
    scbssfbhsxrq VARCHAR(10) COMMENT '生产标识是否包含有效期',
    tscchcztj VARCHAR(200) COMMENT '储存条件',
    tsccsm VARCHAR(500) COMMENT '储存说明',
    version_number INT COMMENT '版本号',
    version_time DATE COMMENT '版本时间',
    version_status VARCHAR(20) COMMENT '版本状态',
    correction_number INT COMMENT '更正次数',
    correction_remark TEXT COMMENT '更正备注',
    correction_time DATE COMMENT '更正时间',
    
    -- 嵌套字段标记
    has_packing_list BOOLEAN DEFAULT FALSE COMMENT '是否有包装列表',
    has_storage_list BOOLEAN DEFAULT FALSE COMMENT '是否有储存条件列表',
    has_clinical_list BOOLEAN DEFAULT FALSE COMMENT '是否有临床尺寸列表',
    
    -- 索引
    UNIQUE KEY idx_device_record_key (device_record_key),
    KEY idx_zxxsdycpbs (zxxsdycpbs),
    KEY idx_cpbsbmtxmc (cpbsbmtxmc),
    KEY idx_cpmctymc (cpmctymc),
    KEY idx_ylqxzcrbarmc (ylqxzcrbarmc),
    KEY idx_zczbhhzbapzbh (zczbhhzbapzbh(191)),
    KEY idx_version_time (version_time),
    KEY idx_version_status (version_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI设备主表';

-- ============================================
-- 2. 包装列表表
-- ============================================
CREATE TABLE IF NOT EXISTS udi_packing_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_record_key VARCHAR(100) NOT NULL COMMENT '设备记录键',
    bzcpbs VARCHAR(100) COMMENT '包装产品标识',
    cpbzjb VARCHAR(50) COMMENT '产品包装级别',
    bznhxyjcpbssl INT COMMENT '包装内含小一级产品标识数量',
    bznhxyjbzcpbs VARCHAR(100) COMMENT '包装内含小一级包装产品标识',
    
    KEY idx_device_record_key (device_record_key),
    KEY idx_bzcpbs (bzcpbs)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI包装列表表';

-- ============================================
-- 3. 储存条件表
-- ============================================
CREATE TABLE IF NOT EXISTS udi_storage_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_record_key VARCHAR(100) NOT NULL COMMENT '设备记录键',
    cchcztj VARCHAR(200) COMMENT '储存或操作条件',
    zdz VARCHAR(50) COMMENT '最低值',
    zgz VARCHAR(50) COMMENT '最高值',
    jldw VARCHAR(20) COMMENT '计量单位',
    
    KEY idx_device_record_key (device_record_key),
    KEY idx_cchcztj (cchcztj)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI储存条件表';

-- ============================================
-- 4. 临床尺寸表
-- ============================================
CREATE TABLE IF NOT EXISTS udi_clinical_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_record_key VARCHAR(100) NOT NULL COMMENT '设备记录键',
    lcsycclx VARCHAR(100) COMMENT '临床使用尺寸类型',
    ccz VARCHAR(50) COMMENT '尺寸值',
    ccdw VARCHAR(20) COMMENT '尺寸单位',
    
    KEY idx_device_record_key (device_record_key),
    KEY idx_lcsycclx (lcsycclx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI临床尺寸表';

-- ============================================
-- 5. 联系人表
-- ============================================
CREATE TABLE IF NOT EXISTS udi_contacts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    device_record_key VARCHAR(100) NOT NULL COMMENT '设备记录键',
    qylxrcz VARCHAR(100) COMMENT '联系人传真',
    qylxryx VARCHAR(200) COMMENT '联系人邮箱',
    qylxrdh VARCHAR(100) COMMENT '联系人电话',
    
    KEY idx_device_record_key (device_record_key),
    KEY idx_qylxryx (qylxryx),
    KEY idx_qylxrdh (qylxrdh)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='UDI联系人表';

-- ============================================
-- 6. 数据导入日志表
-- ============================================
CREATE TABLE IF NOT EXISTS import_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    import_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_name VARCHAR(200),
    total_records INT,
    success_records INT,
    failed_records INT,
    status ENUM('running', 'completed', 'completed_with_errors', 'failed'),
    error_message TEXT,
    duration_seconds INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据导入日志表';

-- ============================================
-- 7. 单条导入错误记录表
-- ============================================
CREATE TABLE IF NOT EXISTS import_error_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    error_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_name VARCHAR(200) NOT NULL,
    device_record_key VARCHAR(100),
    error_code INT,
    affected_column VARCHAR(100),
    error_message TEXT NOT NULL,

    KEY idx_error_file_name (file_name),
    KEY idx_error_device_record_key (device_record_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='单条数据导入错误记录';
