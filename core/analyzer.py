import re
from typing import List, Dict


class RequirementAnalyzer:
    """预分析需求文档，提取关键信息"""

    def analyze(self, requirement_text: str, prd_text: str) -> Dict:
        """分析文档并提取结构化信息"""
        analysis = {
            "modules": self._extract_modules(requirement_text + prd_text),
            "user_stories": self._extract_user_stories(requirement_text),
            "business_rules": self._extract_business_rules(requirement_text),
            "ui_components": self._extract_ui_components(prd_text),
            "data_flows": self._extract_data_flows(requirement_text),
            "risk_areas": []
        }

        # 识别高风险区域
        analysis["risk_areas"] = self._identify_risks(analysis)

        return analysis

    def _extract_modules(self, text: str) -> List[str]:
        """提取功能模块"""
        patterns = [
            r'【?模块】?\s*[：:]\s*([^\n]+)',
            r'##?\s*([^\n]+?)(?:模块|功能)',
            r'(?:模块|功能)[：:]\s*([^\n]+)'
        ]
        modules = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            modules.extend(matches)
        return list(set(modules))[:20]  # 去重并限制数量

    def _extract_user_stories(self, text: str) -> List[Dict]:
        """提取用户故事"""
        pattern = r'(?:作为|As)\s*([^\n,，]+)[,，]\s*(?:我想|I want|我希望|I would like)\s*([^\n,，]+)[,，]\s*(?:以便|so that|从而)\s*([^\n]+)'
        stories = []
        for match in re.finditer(pattern, text, re.IGNORECASE):
            stories.append({
                "role": match.group(1).strip(),
                "action": match.group(2).strip(),
                "benefit": match.group(3).strip()
            })
        return stories

    def _extract_business_rules(self, text: str) -> List[str]:
        """提取业务规则"""
        patterns = [
            r'(?:规则|限制|约束|必须|应该|只能)[：:]\s*([^\n]+)',
            r'(?:Rule|Constraint)[：:]\s*([^\n]+)',
            r'【业务规则】\s*([^\n]+)'
        ]
        rules = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            rules.extend(matches)
        return rules

    def _extract_ui_components(self, prd_text: str) -> List[Dict]:
        """提取UI组件"""
        components = []
        # 按钮
        buttons = re.findall(r'(?:按钮|Button)[：:]\s*([^\n,，]+)', prd_text, re.IGNORECASE)
        for btn in buttons:
            components.append({"type": "button", "name": btn.strip()})

        # 输入框
        inputs = re.findall(r'(?:输入框|Input|字段)[：:]\s*([^\n,，]+)', prd_text, re.IGNORECASE)
        for inp in inputs:
            components.append({"type": "input", "name": inp.strip()})

        # 页面
        pages = re.findall(r'(?:页面|Page|Screen)[：:]\s*([^\n,，]+)', prd_text, re.IGNORECASE)
        for page in pages:
            components.append({"type": "page", "name": page.strip()})

        return components

    def _extract_data_flows(self, text: str) -> List[str]:
        """提取数据流/流程"""
        flows = []
        # 流程步骤
        steps = re.findall(r'(?:步骤|Step)\s*\d+[：:]\s*([^\n]+)', text, re.IGNORECASE)
        flows.extend(steps)

        # 状态流转
        states = re.findall(r'(?:状态|State)[：:]\s*([^\n]+)', text, re.IGNORECASE)
        flows.extend(states)

        return flows

    def _identify_risks(self, analysis: Dict) -> List[str]:
        """识别潜在风险区域"""
        risks = []

        # 复杂业务规则
        if len(analysis["business_rules"]) > 10:
            risks.append("业务规则复杂（>10条），需重点测试规则冲突")

        # 多模块交互
        if len(analysis["modules"]) > 5:
            risks.append("模块较多，需重点测试集成场景")

        # 数据流复杂
        if len(analysis["data_flows"]) > 8:
            risks.append("流程步骤较多，需重点测试流程中断和回退")

        return risks