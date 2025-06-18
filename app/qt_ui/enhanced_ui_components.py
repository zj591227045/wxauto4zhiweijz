"""
增强版UI组件模块
包含美化后的可复用UI组件，具有现代化视觉效果
"""

import math
from PyQt6.QtWidgets import (QPushButton, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QDialog, QLineEdit, QComboBox, QCheckBox,
                             QSpinBox, QTextEdit, QRadioButton, QButtonGroup,
                             QGraphicsDropShadowEffect, QGraphicsBlurEffect)
from PyQt6.QtCore import (Qt, pyqtSignal, QTimer, QPropertyAnimation, QRect,
                          QEasingCurve, QPoint, QPointF, QParallelAnimationGroup,
                          QSequentialAnimationGroup, QVariantAnimation, pyqtProperty)
from PyQt6.QtGui import (QFont, QPalette, QColor, QPainter, QPen, QBrush,
                         QLinearGradient, QRadialGradient, QPainterPath,
                         QPixmap, QConicalGradient)


class EnhancedCircularButton(QPushButton):
    """增强版圆形按钮 - 具有磨砂玻璃效果、波纹动画和动态阴影"""
    
    def __init__(self, text="开始监听", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(140, 140)  # 增大尺寸以容纳阴影效果
        self.is_listening = False
        self._hover_scale = 1.0
        self._ripple_radius = 0
        self._ripple_opacity = 0
        self._pulse_value = 0
        
        # 设置基础样式
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: white;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Microsoft YaHei';
            }
        """)
        
        # 添加阴影效果
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(20)
        self.shadow_effect.setOffset(0, 8)
        self.shadow_effect.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(self.shadow_effect)
        
        # 悬停动画
        self.hover_animation = QPropertyAnimation(self, b"hover_scale")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 按下缩放动画
        self.press_animation = QPropertyAnimation(self, b"hover_scale")
        self.press_animation.setDuration(100)
        self.press_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 波纹动画
        self.ripple_animation = QParallelAnimationGroup()
        
        self.ripple_radius_anim = QPropertyAnimation(self, b"ripple_radius")
        self.ripple_radius_anim.setDuration(600)
        self.ripple_radius_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.ripple_opacity_anim = QPropertyAnimation(self, b"ripple_opacity")
        self.ripple_opacity_anim.setDuration(600)
        self.ripple_opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.ripple_animation.addAnimation(self.ripple_radius_anim)
        self.ripple_animation.addAnimation(self.ripple_opacity_anim)
        
        # 脉冲动画（监听状态）
        self.pulse_animation = QPropertyAnimation(self, b"pulse_value")
        self.pulse_animation.setDuration(2000)
        self.pulse_animation.setLoopCount(-1)  # 无限循环
        self.pulse_animation.setKeyValueAt(0, 0)
        self.pulse_animation.setKeyValueAt(0.5, 1)
        self.pulse_animation.setKeyValueAt(1, 0)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # 属性设置
        self.setProperty("hover_scale", 1.0)
        self.setProperty("ripple_radius", 0)
        self.setProperty("ripple_opacity", 0)
        self.setProperty("pulse_value", 0)
    
    def paintEvent(self, event):
        """自定义绘制 - 实现磨砂玻璃效果和动画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        center = rect.center()
        base_radius = min(rect.width(), rect.height()) // 2 - 15  # 留出阴影空间
        
        # 应用悬停缩放
        scaled_radius = int(base_radius * self._hover_scale)
        
        # 绘制主按钮
        self._draw_main_button(painter, center, scaled_radius)
        
        # 绘制脉冲效果（监听状态）
        if self.is_listening:
            self._draw_pulse_effect(painter, center, scaled_radius)
        
        # 绘制波纹效果
        if self._ripple_radius > 0:
            self._draw_ripple_effect(painter, center)
        
        # 绘制文字
        self._draw_text(painter, rect)
    
    def _draw_main_button(self, painter, center, radius):
        """绘制主按钮 - 磨砂玻璃效果"""
        # 外圈渐变（磨砂玻璃边框）
        outer_gradient = QRadialGradient(center.x(), center.y(), radius + 5)
        if self.is_listening:
            outer_gradient.setColorAt(0, QColor(255, 107, 107, 200))
            outer_gradient.setColorAt(0.8, QColor(255, 77, 77, 150))
            outer_gradient.setColorAt(1, QColor(255, 47, 47, 100))
        else:
            outer_gradient.setColorAt(0, QColor(59, 130, 246, 200))
            outer_gradient.setColorAt(0.8, QColor(37, 99, 235, 150))
            outer_gradient.setColorAt(1, QColor(29, 78, 216, 100))
        
        painter.setBrush(QBrush(outer_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 50), 2))
        painter.drawEllipse(center.x() - radius - 3, center.y() - radius - 3, 
                          (radius + 3) * 2, (radius + 3) * 2)
        
        # 内圈主体（磨砂玻璃效果）
        inner_gradient = QRadialGradient(center.x(), center.y(), radius)
        if self.is_listening:
            inner_gradient.setColorAt(0, QColor(255, 87, 87, 220))
            inner_gradient.setColorAt(0.6, QColor(255, 67, 67, 180))
            inner_gradient.setColorAt(1, QColor(255, 47, 47, 140))
        else:
            inner_gradient.setColorAt(0, QColor(79, 150, 255, 220))
            inner_gradient.setColorAt(0.6, QColor(59, 130, 246, 180))
            inner_gradient.setColorAt(1, QColor(37, 99, 235, 140))
        
        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawEllipse(center.x() - radius, center.y() - radius, 
                          radius * 2, radius * 2)
        
        # 高光效果
        highlight_gradient = QRadialGradient(
            center.x() - radius // 3, center.y() - radius // 3, radius // 2
        )
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 60))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        
        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center.x() - radius, center.y() - radius, 
                          radius * 2, radius * 2)
    
    def _draw_pulse_effect(self, painter, center, radius):
        """绘制脉冲效果"""
        pulse_radius = radius + int(20 * self._pulse_value)
        pulse_opacity = int(100 * (1 - self._pulse_value))
        
        pulse_gradient = QRadialGradient(center.x(), center.y(), pulse_radius)
        pulse_gradient.setColorAt(0, QColor(255, 87, 87, 0))
        pulse_gradient.setColorAt(0.8, QColor(255, 87, 87, pulse_opacity))
        pulse_gradient.setColorAt(1, QColor(255, 87, 87, 0))
        
        painter.setBrush(QBrush(pulse_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center.x() - pulse_radius, center.y() - pulse_radius,
                          pulse_radius * 2, pulse_radius * 2)
    
    def _draw_ripple_effect(self, painter, center):
        """绘制波纹效果"""
        ripple_color = QColor(255, 255, 255, int(self._ripple_opacity))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(ripple_color, 3))
        painter.drawEllipse(int(center.x() - self._ripple_radius), int(center.y() - self._ripple_radius),
                          int(self._ripple_radius * 2), int(self._ripple_radius * 2))
    
    def _draw_text(self, painter, rect):
        """绘制文字"""
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        text = "停止监听" if self.is_listening else "开始监听"
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        # 只有在没有按下时才执行悬停动画
        if not self.press_animation.state() == QPropertyAnimation.State.Running:
            self.hover_animation.setStartValue(self._hover_scale)
            self.hover_animation.setEndValue(1.05)
            self.hover_animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        # 只有在没有按下时才执行离开动画
        if not self.press_animation.state() == QPropertyAnimation.State.Running:
            self.hover_animation.setStartValue(self._hover_scale)
            self.hover_animation.setEndValue(1.0)
            self.hover_animation.start()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 触发按下缩放和波纹动画"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 停止当前的悬停动画
            self.hover_animation.stop()

            # 启动按下缩放动画（缩小到0.95倍）
            self.press_animation.setStartValue(self._hover_scale)
            self.press_animation.setEndValue(0.95)
            self.press_animation.start()

            # 启动波纹动画
            self.start_ripple_animation()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件 - 恢复按钮大小"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 停止按下动画
            self.press_animation.stop()

            # 恢复到悬停状态的大小
            target_scale = 1.05 if self.underMouse() else 1.0
            self.press_animation.setStartValue(self._hover_scale)
            self.press_animation.setEndValue(target_scale)
            self.press_animation.setDuration(150)  # 稍快的恢复动画
            self.press_animation.start()
        super().mouseReleaseEvent(event)
    
    def start_ripple_animation(self):
        """启动波纹动画"""
        self.ripple_radius_anim.setStartValue(0)
        self.ripple_radius_anim.setEndValue(80)
        
        self.ripple_opacity_anim.setStartValue(255)
        self.ripple_opacity_anim.setEndValue(0)
        
        self.ripple_animation.start()
    
    def set_listening_state(self, is_listening: bool):
        """设置监听状态"""
        self.is_listening = is_listening
        
        if is_listening:
            self.pulse_animation.start()
            # 更新阴影颜色为红色
            self.shadow_effect.setColor(QColor(255, 87, 87, 100))
        else:
            self.pulse_animation.stop()
            self._pulse_value = 0
            # 恢复蓝色阴影
            self.shadow_effect.setColor(QColor(59, 130, 246, 80))
        
        self.update()
    
    # PyQt6属性定义
    @pyqtProperty(float)
    def hover_scale(self):
        return self._hover_scale

    @hover_scale.setter
    def hover_scale(self, value):
        self._hover_scale = value
        self.update()

    @pyqtProperty(float)
    def ripple_radius(self):
        return self._ripple_radius

    @ripple_radius.setter
    def ripple_radius(self, value):
        self._ripple_radius = value
        self.update()

    @pyqtProperty(float)
    def ripple_opacity(self):
        return self._ripple_opacity

    @ripple_opacity.setter
    def ripple_opacity(self, value):
        self._ripple_opacity = value
        self.update()

    @pyqtProperty(float)
    def pulse_value(self):
        return self._pulse_value

    @pulse_value.setter
    def pulse_value(self, value):
        self._pulse_value = value
        self.update()


class EnhancedStatusIndicator(QWidget):
    """增强版状态指示器 - 磨砂玻璃效果和脉冲动画"""

    clicked = pyqtSignal()

    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.is_active = False
        self.is_blinking = False
        self.blink_state = False
        self._hover_elevation = 0
        self._pulse_value = 0

        self.setFixedSize(220, 90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 添加阴影效果
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(15)
        self.shadow_effect.setOffset(0, 4)
        self.shadow_effect.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(self.shadow_effect)

        # 悬停动画
        self.hover_animation = QPropertyAnimation(self, b"hover_elevation")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 闪烁动画
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)

        # 脉冲动画（指示灯）
        self.pulse_animation = QPropertyAnimation(self, b"pulse_value")
        self.pulse_animation.setDuration(2000)
        self.pulse_animation.setLoopCount(-1)
        self.pulse_animation.setKeyValueAt(0, 0)
        self.pulse_animation.setKeyValueAt(0.5, 1)
        self.pulse_animation.setKeyValueAt(1, 0)
        self.pulse_animation.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.setProperty("hover_elevation", 0)
        self.setProperty("pulse_value", 0)

    def paintEvent(self, event):
        """自定义绘制 - 磨砂玻璃卡片效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)  # 为阴影留出空间

        # 绘制磨砂玻璃背景
        self._draw_glass_background(painter, rect)

        # 绘制边框发光效果
        if self.is_active:
            self._draw_border_glow(painter, rect)

        # 绘制状态指示灯
        self._draw_status_indicator(painter, rect)

        # 绘制文字内容
        self._draw_text_content(painter, rect)

    def _draw_glass_background(self, painter, rect):
        """绘制磨砂玻璃背景"""
        # 主背景渐变
        background_gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        background_gradient.setColorAt(0, QColor(45, 55, 72, 200))
        background_gradient.setColorAt(0.5, QColor(30, 41, 59, 180))
        background_gradient.setColorAt(1, QColor(15, 23, 42, 160))

        painter.setBrush(QBrush(background_gradient))
        painter.setPen(QPen(QColor(74, 85, 104, 150), 1))
        painter.drawRoundedRect(rect, 12, 12)

        # 高光效果
        highlight_rect = rect.adjusted(1, 1, -1, -rect.height()//2)
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 40))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(highlight_rect, 11, 11)

    def _draw_border_glow(self, painter, rect):
        """绘制边框发光效果"""
        glow_color = QColor(34, 197, 94, 100) if self.is_active else QColor(156, 163, 175, 50)

        for i in range(3):
            glow_rect = rect.adjusted(-i, -i, i, i)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(glow_color, 1))
            painter.drawRoundedRect(glow_rect, 12 + i, 12 + i)
            glow_color.setAlpha(glow_color.alpha() // 2)

    def _draw_status_indicator(self, painter, rect):
        """绘制状态指示灯"""
        indicator_center = QPoint(rect.left() + 20, rect.top() + 20)
        base_radius = 8

        if self.is_active:
            # 活跃状态 - 绿色指示灯
            if self.is_blinking and self.blink_state:
                indicator_color = QColor(34, 197, 94, 255)
            else:
                indicator_color = QColor(22, 163, 74, 220)

            # 脉冲效果
            if self._pulse_value > 0:
                pulse_radius = base_radius + int(6 * self._pulse_value)
                pulse_opacity = int(80 * (1 - self._pulse_value))
                pulse_gradient = QRadialGradient(indicator_center.x(), indicator_center.y(), pulse_radius)
                pulse_gradient.setColorAt(0, QColor(34, 197, 94, 0))
                pulse_gradient.setColorAt(0.7, QColor(34, 197, 94, pulse_opacity))
                pulse_gradient.setColorAt(1, QColor(34, 197, 94, 0))

                painter.setBrush(QBrush(pulse_gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(indicator_center.x() - pulse_radius,
                                  indicator_center.y() - pulse_radius,
                                  pulse_radius * 2, pulse_radius * 2)
        else:
            # 非活跃状态 - 灰色指示灯
            indicator_color = QColor(156, 163, 175, 180)

        # 绘制主指示灯
        indicator_gradient = QRadialGradient(indicator_center.x(), indicator_center.y(), base_radius)
        indicator_gradient.setColorAt(0, indicator_color)
        indicator_gradient.setColorAt(0.7, indicator_color.darker(120))
        indicator_gradient.setColorAt(1, indicator_color.darker(150))

        painter.setBrush(QBrush(indicator_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawEllipse(indicator_center.x() - base_radius,
                          indicator_center.y() - base_radius,
                          base_radius * 2, base_radius * 2)

    def _draw_text_content(self, painter, rect):
        """绘制文字内容"""
        # 绘制标题
        painter.setPen(QColor(241, 245, 249))
        painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        title_rect = QRect(rect.left() + 45, rect.top() + 12, rect.width() - 55, 25)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)

        # 绘制副标题
        painter.setPen(QColor(156, 163, 175))
        painter.setFont(QFont("Microsoft YaHei", 9))
        subtitle_rect = QRect(rect.left() + 45, rect.top() + 35, rect.width() - 55, 45)
        painter.drawText(subtitle_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self.subtitle)

    def enterEvent(self, event):
        """鼠标进入事件"""
        self.hover_animation.setStartValue(self._hover_elevation)
        self.hover_animation.setEndValue(8)
        self.hover_animation.start()

        # 更新阴影效果
        self.shadow_effect.setOffset(0, 8)
        self.shadow_effect.setBlurRadius(20)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.hover_animation.setStartValue(self._hover_elevation)
        self.hover_animation.setEndValue(0)
        self.hover_animation.start()

        # 恢复阴影效果
        self.shadow_effect.setOffset(0, 4)
        self.shadow_effect.setBlurRadius(15)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_active(self, active: bool, blinking: bool = False):
        """设置活跃状态"""
        self.is_active = active
        self.is_blinking = blinking

        if blinking and active:
            self.blink_timer.start(500)
            self.pulse_animation.start()
        else:
            self.blink_timer.stop()
            self.pulse_animation.stop()
            self.blink_state = False
            self._pulse_value = 0

        self.update()

    def set_subtitle(self, subtitle: str):
        """设置副标题"""
        self.subtitle = subtitle
        self.update()

    def toggle_blink(self):
        """切换闪烁状态"""
        self.blink_state = not self.blink_state
        self.update()

    # PyQt6属性定义
    @pyqtProperty(float)
    def hover_elevation(self):
        return self._hover_elevation

    @hover_elevation.setter
    def hover_elevation(self, value):
        self._hover_elevation = value
        self.update()

    @pyqtProperty(float)
    def pulse_value(self):
        return self._pulse_value

    @pulse_value.setter
    def pulse_value(self, value):
        self._pulse_value = value
        self.update()


class EnhancedStatCard(QWidget):
    """增强版统计卡片 - 悬停上浮效果和数字动画"""

    def __init__(self, title, value=0, parent=None):
        super().__init__(parent)
        self.title = title
        self._current_value = value
        self.target_value = value
        self._hover_elevation = 0
        self._number_scale = 1.0

        self.setFixedSize(130, 70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # 添加阴影效果
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(10)
        self.shadow_effect.setOffset(0, 2)
        self.shadow_effect.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(self.shadow_effect)

        # 悬停动画
        self.hover_animation = QPropertyAnimation(self, b"hover_elevation")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 数值变化动画
        self.value_animation = QPropertyAnimation(self, b"current_value")
        self.value_animation.setDuration(800)
        self.value_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 数字缩放动画
        self.scale_animation = QPropertyAnimation(self, b"number_scale")
        self.scale_animation.setDuration(300)
        self.scale_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        self.setProperty("hover_elevation", 0)
        self.setProperty("current_value", value)
        self.setProperty("number_scale", 1.0)

    def paintEvent(self, event):
        """自定义绘制 - 磨砂玻璃卡片"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        # 绘制磨砂玻璃背景
        self._draw_glass_background(painter, rect)

        # 绘制数值
        self._draw_value(painter, rect)

        # 绘制标题
        self._draw_title(painter, rect)

    def _draw_glass_background(self, painter, rect):
        """绘制磨砂玻璃背景"""
        # 主背景渐变
        background_gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        background_gradient.setColorAt(0, QColor(30, 41, 59, 200))
        background_gradient.setColorAt(0.5, QColor(51, 65, 85, 180))
        background_gradient.setColorAt(1, QColor(71, 85, 105, 160))

        painter.setBrush(QBrush(background_gradient))
        painter.setPen(QPen(QColor(100, 116, 139, 120), 1))
        painter.drawRoundedRect(rect, 8, 8)

        # 高光效果
        highlight_rect = rect.adjusted(1, 1, -1, -rect.height()//2)
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 30))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.setBrush(QBrush(highlight_gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(highlight_rect, 7, 7)

    def _draw_value(self, painter, rect):
        """绘制数值 - 带缩放效果"""
        painter.save()

        # 应用缩放变换
        center = rect.center()
        painter.translate(center)
        painter.scale(self._number_scale, self._number_scale)
        painter.translate(-center)

        # 数值渐变色
        value_gradient = QLinearGradient(0, rect.top(), 0, rect.top() + 30)
        value_gradient.setColorAt(0, QColor(59, 130, 246))
        value_gradient.setColorAt(1, QColor(37, 99, 235))

        painter.setPen(QPen(QBrush(value_gradient), 1))
        painter.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))

        value_rect = QRect(0, rect.top() + 8, rect.width(), 35)
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignCenter, str(int(self._current_value)))

        painter.restore()

    def _draw_title(self, painter, rect):
        """绘制标题"""
        painter.setPen(QColor(156, 163, 175))
        painter.setFont(QFont("Microsoft YaHei", 9))
        title_rect = QRect(0, rect.top() + 48, rect.width(), 20)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.title)

    def enterEvent(self, event):
        """鼠标进入事件"""
        self.hover_animation.setStartValue(self._hover_elevation)
        self.hover_animation.setEndValue(6)
        self.hover_animation.start()

        # 更新阴影效果
        self.shadow_effect.setOffset(0, 6)
        self.shadow_effect.setBlurRadius(15)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.hover_animation.setStartValue(self._hover_elevation)
        self.hover_animation.setEndValue(0)
        self.hover_animation.start()

        # 恢复阴影效果
        self.shadow_effect.setOffset(0, 2)
        self.shadow_effect.setBlurRadius(10)
        super().leaveEvent(event)

    def set_value(self, value):
        """设置数值 - 带动画效果"""
        if value != self.target_value:
            self.target_value = value

            # 数值变化动画
            self.value_animation.setStartValue(self._current_value)
            self.value_animation.setEndValue(value)
            self.value_animation.start()

            # 数字缩放动画
            self.scale_animation.setStartValue(1.0)
            self.scale_animation.setEndValue(1.2)
            self.scale_animation.finished.connect(self._scale_back)
            self.scale_animation.start()

    def _scale_back(self):
        """缩放回原大小"""
        self.scale_animation.finished.disconnect()
        self.scale_animation.setStartValue(1.2)
        self.scale_animation.setEndValue(1.0)
        self.scale_animation.start()

    # PyQt6属性定义
    @pyqtProperty(float)
    def hover_elevation(self):
        return self._hover_elevation

    @hover_elevation.setter
    def hover_elevation(self, value):
        self._hover_elevation = value
        self.update()

    @pyqtProperty(float)
    def current_value(self):
        return self._current_value

    @current_value.setter
    def current_value(self, value):
        self._current_value = value
        self.update()

    @pyqtProperty(float)
    def number_scale(self):
        return self._number_scale

    @number_scale.setter
    def number_scale(self, value):
        self._number_scale = value
        self.update()


class EnhancedButton(QPushButton):
    """增强版按钮 - 渐变背景和悬停动画"""

    def __init__(self, text="按钮", parent=None):
        super().__init__(text, parent)
        self._hover_intensity = 0

        # 基础样式
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Microsoft YaHei';
                background: transparent;
            }
        """)

        # 添加阴影效果
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(8)
        self.shadow_effect.setOffset(0, 2)
        self.shadow_effect.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(self.shadow_effect)

        # 悬停动画
        self.hover_animation = QPropertyAnimation(self, b"hover_intensity")
        self.hover_animation.setDuration(200)
        self.hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setProperty("hover_intensity", 0)

    def paintEvent(self, event):
        """自定义绘制 - 渐变背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # 背景渐变
        background_gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        base_color = QColor(107, 114, 128)  # 基础灰色

        # 根据悬停强度调整颜色
        hover_factor = self._hover_intensity / 100.0
        lighter_color = base_color.lighter(int(120 + 30 * hover_factor))
        darker_color = base_color.darker(int(110 + 20 * hover_factor))

        background_gradient.setColorAt(0, lighter_color)
        background_gradient.setColorAt(1, darker_color)

        painter.setBrush(QBrush(background_gradient))
        painter.setPen(QPen(QColor(255, 255, 255, int(30 + 20 * hover_factor)), 1))
        painter.drawRoundedRect(rect, 8, 8)

        # 高光效果
        if self._hover_intensity > 0:
            highlight_rect = rect.adjusted(1, 1, -1, -rect.height()//2)
            highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
            highlight_gradient.setColorAt(0, QColor(255, 255, 255, int(20 * hover_factor)))
            highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))

            painter.setBrush(QBrush(highlight_gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(highlight_rect, 7, 7)

        # 绘制文字
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())

    def enterEvent(self, event):
        """鼠标进入事件"""
        self.hover_animation.setStartValue(self._hover_intensity)
        self.hover_animation.setEndValue(100)
        self.hover_animation.start()

        # 增强阴影效果
        self.shadow_effect.setOffset(0, 4)
        self.shadow_effect.setBlurRadius(12)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.hover_animation.setStartValue(self._hover_intensity)
        self.hover_animation.setEndValue(0)
        self.hover_animation.start()

        # 恢复阴影效果
        self.shadow_effect.setOffset(0, 2)
        self.shadow_effect.setBlurRadius(8)
        super().leaveEvent(event)

    # PyQt6属性定义
    @pyqtProperty(float)
    def hover_intensity(self):
        return self._hover_intensity

    @hover_intensity.setter
    def hover_intensity(self, value):
        self._hover_intensity = value
        self.update()


class TexturedBackground(QWidget):
    """纹理背景组件 - 深色纹理效果"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._texture_offset = 0

        # 纹理动画（可选）
        self.texture_animation = QPropertyAnimation(self, b"texture_offset")
        self.texture_animation.setDuration(20000)  # 20秒循环
        self.texture_animation.setLoopCount(-1)
        self.texture_animation.setStartValue(0)
        self.texture_animation.setEndValue(100)

    def paintEvent(self, event):
        """绘制纹理背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # 主背景渐变
        main_gradient = QLinearGradient(0, 0, 0, rect.height())
        main_gradient.setColorAt(0, QColor(15, 23, 42))   # slate-900
        main_gradient.setColorAt(0.5, QColor(30, 41, 59)) # slate-800
        main_gradient.setColorAt(1, QColor(51, 65, 85))   # slate-700

        painter.fillRect(rect, QBrush(main_gradient))

        # 添加纹理图案
        self._draw_texture_pattern(painter, rect)

        # 添加微妙的噪点效果
        self._draw_noise_pattern(painter, rect)

    def _draw_texture_pattern(self, painter, rect):
        """绘制纹理图案"""
        painter.save()

        # 设置半透明画笔
        painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 绘制对角线纹理
        spacing = 20
        offset = int(self._texture_offset) % (spacing * 2)

        for i in range(-spacing, rect.width() + rect.height(), spacing):
            x1 = i - offset
            y1 = 0
            x2 = i + rect.height() - offset
            y2 = rect.height()
            painter.drawLine(x1, y1, x2, y2)

        painter.restore()

    def _draw_noise_pattern(self, painter, rect):
        """绘制噪点图案"""
        painter.save()

        # 创建随机噪点
        import random
        random.seed(42)  # 固定种子确保一致性

        painter.setPen(Qt.PenStyle.NoPen)

        for _ in range(rect.width() * rect.height() // 2000):  # 控制噪点密度
            x = random.randint(0, rect.width())
            y = random.randint(0, rect.height())
            alpha = random.randint(5, 15)

            painter.setBrush(QBrush(QColor(255, 255, 255, alpha)))
            painter.drawEllipse(x, y, 1, 1)

        painter.restore()

    def start_texture_animation(self):
        """启动纹理动画"""
        self.texture_animation.start()

    def stop_texture_animation(self):
        """停止纹理动画"""
        self.texture_animation.stop()

    # PyQt6属性定义
    @pyqtProperty(float)
    def texture_offset(self):
        return self._texture_offset

    @texture_offset.setter
    def texture_offset(self, value):
        self._texture_offset = value
        self.update()
