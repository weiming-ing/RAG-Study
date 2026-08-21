package com.ragstudy.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.ragstudy.model.entity.KnowledgeDocument;
import com.ragstudy.model.entity.ParseTask;
import com.ragstudy.model.vo.ParseTaskVO;
import com.ragstudy.repository.KnowledgeDocumentMapper;
import com.ragstudy.repository.ParseTaskMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class ParseTaskService {

    private static final Logger log = LoggerFactory.getLogger(ParseTaskService.class);

    private final ParseTaskMapper parseTaskMapper;
    private final KnowledgeDocumentMapper documentMapper;

    public ParseTaskService(ParseTaskMapper parseTaskMapper, KnowledgeDocumentMapper documentMapper) {
        this.parseTaskMapper = parseTaskMapper;
        this.documentMapper = documentMapper;
    }

    public IPage<ParseTaskVO> listTasks(int pageNum, int pageSize, String status) {
        Page<ParseTask> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<ParseTask> wrapper = new LambdaQueryWrapper<>();
        if (status != null && !status.isEmpty()) {
            wrapper.eq(ParseTask::getStatus, status);
        }
        wrapper.orderByDesc(ParseTask::getCreateTime);

        IPage<ParseTask> taskPage = parseTaskMapper.selectPage(page, wrapper);
        return taskPage.convert(this::toVO);
    }

    public List<ParseTaskVO> getTasksByDocumentId(String documentId) {
        List<ParseTask> tasks = parseTaskMapper.selectByDocumentId(documentId);
        return tasks.stream().map(this::toVO).collect(Collectors.toList());
    }

    @Transactional
    public ParseTask createTask(String documentId, String taskType) {
        ParseTask task = new ParseTask();
        task.setDocumentId(documentId);
        task.setTaskType(taskType);
        task.setStatus("PENDING");
        task.setProgress(0);
        task.setRetryCount(0);
        task.setMaxRetry(3);
        parseTaskMapper.insert(task);
        return task;
    }

    @Transactional
    public void startTask(Long taskId) {
        ParseTask task = parseTaskMapper.selectById(taskId);
        if (task != null) {
            task.setStatus("RUNNING");
            task.setStartTime(LocalDateTime.now());
            parseTaskMapper.updateById(task);
        }
    }

    @Transactional
    public void completeTask(Long taskId) {
        ParseTask task = parseTaskMapper.selectById(taskId);
        if (task != null) {
            task.setStatus("SUCCESS");
            task.setProgress(100);
            task.setEndTime(LocalDateTime.now());
            parseTaskMapper.updateById(task);
        }
    }

    @Transactional
    public void failTask(Long taskId, String errorMsg) {
        ParseTask task = parseTaskMapper.selectById(taskId);
        if (task != null) {
            task.setStatus("FAILED");
            task.setErrorMsg(errorMsg);
            task.setEndTime(LocalDateTime.now());
            parseTaskMapper.updateById(task);
        }
    }

    @Transactional
    public void updateProgress(Long taskId, int progress) {
        ParseTask task = parseTaskMapper.selectById(taskId);
        if (task != null) {
            task.setProgress(progress);
            parseTaskMapper.updateById(task);
        }
    }

    private ParseTaskVO toVO(ParseTask task) {
        ParseTaskVO vo = new ParseTaskVO();
        vo.setId(task.getId());
        vo.setDocumentId(task.getDocumentId());
        vo.setTaskType(task.getTaskType());
        vo.setStatus(task.getStatus());
        vo.setProgress(task.getProgress());
        vo.setErrorMsg(task.getErrorMsg());
        vo.setRetryCount(task.getRetryCount());
        vo.setCreateTime(task.getCreateTime());
        vo.setStartTime(task.getStartTime());
        vo.setEndTime(task.getEndTime());

        KnowledgeDocument doc = null;
        try {
            doc = documentMapper.selectById(Long.parseLong(task.getDocumentId()));
        } catch (NumberFormatException e) {
            log.warn("解析文档ID失败: {}", task.getDocumentId());
        }
        if (doc != null) {
            vo.setDocumentName(doc.getFileName());
        }
        return vo;
    }
}