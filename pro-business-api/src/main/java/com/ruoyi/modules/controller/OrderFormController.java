package com.ruoyi.modules.controller;

import java.util.Arrays;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.entity.OrderForm;
import com.ruoyi.modules.service.IOrderFormService;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;

 /**
 * @Description: 下单单据信息
 * @Author: ret-boot
 * @Date:   2024-04-28
 * @Version: V1.0
 */
@Api(tags="下单单据信息")
@RestController
@RequestMapping("/ecapi/orderForm")
@Slf4j
public class OrderFormController{
	@Autowired
	private IOrderFormService orderFormService;

	/**
	 * 分页列表查询
	 *
	 * @param orderForm
	 * @param pageNo
	 * @param pageSize
	 * @return
	 */
	@ApiOperation(value="下单单据信息-分页列表查询", notes="下单单据信息-分页列表查询")
	@GetMapping(value = "/list")
	public Result<?> queryPageList(OrderForm orderForm,
                                   @RequestParam(name="pageNo", defaultValue="1") Integer pageNo,
                                   @RequestParam(name="pageSize", defaultValue="10") Integer pageSize) {
		QueryWrapper<OrderForm> queryWrapper = new QueryWrapper<>();

		Page<OrderForm> page = new Page<>(pageNo, pageSize);
		IPage<OrderForm> pageList = orderFormService.page(page, queryWrapper);
		return Result.OK(pageList);
	}

	/**
	 *   添加
	 *
	 * @param orderForm
	 * @return
	 */
	@ApiOperation(value="下单单据信息-添加", notes="下单单据信息-添加")
	@PostMapping(value = "/add")
	public Result<?> add(@RequestBody OrderForm orderForm) {
		orderFormService.save(orderForm);
		return Result.OK("添加成功！");
	}

	/**
	 *  编辑
	 *
	 * @param orderForm
	 * @return
	 */
	@ApiOperation(value="下单单据信息-编辑", notes="下单单据信息-编辑")
	@PutMapping(value = "/edit")
	public Result<?> edit(@RequestBody OrderForm orderForm) {
		orderFormService.updateById(orderForm);
		return Result.OK("编辑成功!");
	}

	/**
	 *   通过id删除
	 *
	 * @param id
	 * @return
	 */
	@ApiOperation(value="下单单据信息-通过id删除", notes="下单单据信息-通过id删除")
	@DeleteMapping(value = "/delete")
	public Result<?> delete(@RequestParam(name="id",required=true) String id) {
		orderFormService.removeById(id);
		return Result.OK("删除成功!");
	}

	/**
	 *  批量删除
	 *
	 * @param ids
	 * @return
	 */
	@ApiOperation(value="下单单据信息-批量删除", notes="下单单据信息-批量删除")
	@DeleteMapping(value = "/deleteBatch")
	public Result<?> deleteBatch(@RequestParam(name="ids",required=true) String ids) {
		this.orderFormService.removeByIds(Arrays.asList(ids.split(",")));
		return Result.OK("批量删除成功!");
	}

	/**
	 * 通过id查询
	 *
	 * @param id
	 * @return
	 */
	@ApiOperation(value="下单单据信息-通过id查询", notes="下单单据信息-通过id查询")
	@GetMapping(value = "/queryById")
	public Result<?> queryById(@RequestParam(name="id",required=true) String id) {
		OrderForm orderForm = orderFormService.getById(id);
		if(orderForm==null) {
			return Result.error("未找到对应数据");
		}
		return Result.OK(orderForm);
	}
}
