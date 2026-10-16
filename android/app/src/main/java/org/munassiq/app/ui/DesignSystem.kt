package org.munassiq.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Shared native tokens inspired by the user's local Material You/One UI examples. */
@Composable fun MunassiqTheme(dark: Boolean, content: @Composable () -> Unit) {
    val colors = if (dark) darkColorScheme(
        primary=Color(0xFF9BD5C5), onPrimary=Color(0xFF00382C),
        primaryContainer=Color(0xFF155142), onPrimaryContainer=Color(0xFFB7F1DF),
        secondary=Color(0xFFBACCC3), onSecondary=Color(0xFF263D34),
        secondaryContainer=Color(0xFF354D43), onSecondaryContainer=Color(0xFFD6E8DF),
        background=Color(0xFF101512), onBackground=Color(0xFFE0E7E1),
        surface=Color(0xFF151C18), onSurface=Color(0xFFE0E7E1),
        surfaceContainerLowest=Color(0xFF0C110E),surfaceContainerLow=Color(0xFF19211B),
        surfaceContainer=Color(0xFF1E2721),surfaceContainerHigh=Color(0xFF28322B),surfaceContainerHighest=Color(0xFF333D35),
        surfaceDim=Color(0xFF101512),surfaceBright=Color(0xFF354037),
        surfaceVariant=Color(0xFF25342D), onSurfaceVariant=Color(0xFFBFCDC3),
        outline=Color(0xFF89998E), outlineVariant=Color(0xFF3F4D44)
    ) else lightColorScheme(
        primary=Color(0xFF216B56), onPrimary=Color.White,
        primaryContainer=Color(0xFFD5EDE1), onPrimaryContainer=Color(0xFF073C2D),
        secondary=Color(0xFF52665B), onSecondary=Color.White,
        secondaryContainer=Color(0xFFE0EADF), onSecondaryContainer=Color(0xFF263D31),
        background=Color(0xFFF6F8F3), onBackground=Color(0xFF1B2821),
        surface=Color(0xFFFCFDF9), onSurface=Color(0xFF1B2821),
        surfaceContainerLowest=Color.White,surfaceContainerLow=Color(0xFFF0F4ED),
        surfaceContainer=Color(0xFFE9EFE7),surfaceContainerHigh=Color(0xFFE3EAE0),surfaceContainerHighest=Color(0xFFDDE5D9),
        surfaceDim=Color(0xFFD8E1D5),surfaceBright=Color(0xFFFCFDF9),
        surfaceVariant=Color(0xFFE9EFE7), onSurfaceVariant=Color(0xFF4A5D50),
        outline=Color(0xFF75857A), outlineVariant=Color(0xFFD1DBD0)
    )
    val base=Typography()
    MaterialTheme(colorScheme=colors,
        shapes=Shapes(small=RoundedCornerShape(12.dp),medium=RoundedCornerShape(20.dp),large=RoundedCornerShape(26.dp)),
        typography=base.copy(
            headlineLarge=base.headlineLarge.copy(fontFamily=FontFamily.SansSerif,fontWeight=FontWeight.Bold,lineHeight=44.sp),
            headlineSmall=base.headlineSmall.copy(fontFamily=FontFamily.SansSerif,fontWeight=FontWeight.Bold,lineHeight=36.sp),
            titleMedium=base.titleMedium.copy(fontFamily=FontFamily.SansSerif,fontWeight=FontWeight.SemiBold,lineHeight=28.sp),
            bodyLarge=base.bodyLarge.copy(fontFamily=FontFamily.SansSerif,lineHeight=28.sp),
            bodyMedium=base.bodyMedium.copy(fontFamily=FontFamily.SansSerif,lineHeight=25.sp)
        ),content=content)
}

/** Decorative vector-like glyphs; neighboring text provides accessible labels. */
@Composable fun AppGlyph(kind:String, modifier:Modifier=Modifier.size(24.dp), color:Color=MaterialTheme.colorScheme.primary) {
    Canvas(modifier) {
        val unit=size.minDimension/24f
        val stroke=Stroke(width=1.8f*unit)
        fun point(x:Float,y:Float)=Offset(x*unit,y*unit)
        fun line(x:Float,y:Float,x2:Float,y2:Float)=drawLine(color,point(x,y),point(x2,y2),1.8f*unit)
        when(kind) {
            "events" -> {
                drawRoundRect(color,point(3f,5f),Size(18f*unit,16f*unit),CornerRadius(3f*unit),style=stroke)
                line(3f,10f,21f,10f);line(8f,2f,8f,7f);line(16f,2f,16f,7f)
                drawCircle(color,1.5f*unit,point(8f,15f));drawCircle(color,1.5f*unit,point(15f,15f))
            }
            "services" -> {
                drawRoundRect(color,point(4f,4f),Size(16f*unit,17f*unit),CornerRadius(2f*unit),style=stroke)
                line(9f,10f,15f,10f);line(12f,7f,12f,13f);line(10f,21f,10f,17f);line(14f,17f,14f,21f)
            }
            "map" -> {
                drawCircle(color,6f*unit,point(12f,9f),style=stroke)
                drawCircle(color,2f*unit,point(12f,9f),style=stroke)
                line(7f,13f,12f,22f);line(17f,13f,12f,22f)
            }
            "settings" -> {
                for(y in listOf(6f,12f,18f))line(3f,y,21f,y)
                drawCircle(color,2.3f*unit,point(8f,6f));drawCircle(color,2.3f*unit,point(16f,12f));drawCircle(color,2.3f*unit,point(10f,18f))
            }
            else -> {
                drawRoundRect(color,point(5f,3f),Size(14f*unit,19f*unit),CornerRadius(3f*unit),style=stroke)
                line(9f,9f,15f,9f);line(9f,13f,15f,13f);line(9f,17f,13f,17f)
            }
        }
    }
}

@Composable fun BrowseIntro(kind:String) {
    Card(colors=CardDefaults.cardColors(containerColor=MaterialTheme.colorScheme.primaryContainer),shape=RoundedCornerShape(26.dp)) {
        Row(Modifier.fillMaxWidth().padding(22.dp),horizontalArrangement=Arrangement.spacedBy(16.dp),verticalAlignment=Alignment.CenterVertically) {
            Surface(shape=RoundedCornerShape(18.dp),color=MaterialTheme.colorScheme.surface.copy(alpha=.65f)) {
                AppGlyph(kind,Modifier.padding(14.dp).size(30.dp))
            }
            Column(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                Text(label(if(kind=="events")"discover_events" else "discover_services"),style=MaterialTheme.typography.titleLarge)
                Text(label(if(kind=="events")"events_intro" else "services_intro"),style=MaterialTheme.typography.bodyMedium)
            }
        }
    }
}
