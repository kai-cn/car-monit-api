package com.ruoyi.modules.controller;

import java.util.Arrays;
import java.util.List;

import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.entity.ComplaintForm;
import com.ruoyi.modules.entity.EcShopBind;
import com.ruoyi.modules.mapper.EcShopBindMapper;
import com.ruoyi.modules.service.IComplaintFormService;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;

 /**
 * @Description: 投诉单信息
 * @Date:   2024-04-28
 * @Version: V1.0
 */
@Api(tags="投诉单信息")
@RestController
@RequestMapping("/ecapi/complaintForm")
@Slf4j
public class ComplaintFormController{

	@Autowired
	private IComplaintFormService complaintFormService;

	/**
	 * 分页列表查询
	 *
	 * @param complaintForm
	 * @param pageNo
	 * @param pageSize
	 * @return
	 */
	@ApiOperation(value="投诉单信息-分页列表查询", notes="投诉单信息-分页列表查询")
	@GetMapping(value = "/list")
	public Result<?> queryPageList(ComplaintForm complaintForm,
								   @RequestParam(name="pageNo", defaultValue="1") Integer pageNo,
								   @RequestParam(name="pageSize", defaultValue="10") Integer pageSize) {
		QueryWrapper<ComplaintForm> queryWrapper = new QueryWrapper<>();
		Page<ComplaintForm> page = new Page<>(pageNo, pageSize);
		IPage<ComplaintForm> pageList = complaintFormService.page(page, queryWrapper);
		return Result.OK(pageList);
	}

	/**
	 *   添加
	 *
	 * @param complaintForm
	 * @return
	 */
	@ApiOperation(value="投诉单信息-添加", notes="投诉单信息-添加")
	@PostMapping(value = "/add")
	public Result<?> add(@RequestBody ComplaintForm complaintForm) {
		complaintFormService.save(complaintForm);
		return Result.OK("添加成功！");
	}

	/**
	 *  编辑
	 *
	 * @param complaintForm
	 * @return
	 */
	@ApiOperation(value="投诉单信息-编辑", notes="投诉单信息-编辑")
	@PutMapping(value = "/edit")
	public Result<?> edit(@RequestBody ComplaintForm complaintForm) {
		complaintFormService.updateById(complaintForm);
		return Result.OK("编辑成功!");
	}

	/**
	 *   通过id删除
	 *
	 * @param id
	 * @return
	 */
	@ApiOperation(value="投诉单信息-通过id删除", notes="投诉单信息-通过id删除")
	@DeleteMapping(value = "/delete")
	public Result<?> delete(@RequestParam(name="id",required=true) String id) {
		complaintFormService.removeById(id);
		return Result.OK("删除成功!");
	}

	/**
	 *  批量删除
	 *
	 * @param ids
	 * @return
	 */
	@ApiOperation(value="投诉单信息-批量删除", notes="投诉单信息-批量删除")
	@DeleteMapping(value = "/deleteBatch")
	public Result<?> deleteBatch(@RequestParam(name="ids",required=true) String ids) {
		this.complaintFormService.removeByIds(Arrays.asList(ids.split(",")));
		return Result.OK("批量删除成功!");
	}

	/**
	 * 通过id查询
	 *
	 * @param id
	 * @return
	 */
	@ApiOperation(value="投诉单信息-通过id查询", notes="投诉单信息-通过id查询")
	@GetMapping(value = "/queryById")
	public Result<?> queryById(@RequestParam(name="id",required=true) String id) {
		ComplaintForm complaintForm = complaintFormService.getById(id);
		if(complaintForm==null) {
			return Result.error("未找到对应数据");
		}
		return Result.OK(complaintForm);
	}
}
