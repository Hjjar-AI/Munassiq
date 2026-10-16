package org.munassiq.app.ui

import android.content.Context
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener
import org.munassiq.app.R
import org.munassiq.app.data.ApiFailure

class InputProblem(val displayMessage: String) : Exception()

fun normalizedInput(value: String): String = value.map { character ->
    val digit = Character.digit(character, 10)
    when {
        digit >= 0 -> ('0'.code + digit).toChar()
        character == '٫' -> '.'
        character == '−' -> '-'
        else -> character
    }
}.joinToString("").replace("٬", "")

fun localizedError(context: Context, error: Exception): String {
    if (error is kotlinx.coroutines.CancellationException) throw error
    if (error is InputProblem) return error.displayMessage
    if (error !is ApiFailure) return context.getString(when (error) {
        is java.io.IOException -> R.string.connection_failed
        is java.time.DateTimeException -> R.string.invalid_date
        is NumberFormatException -> R.string.invalid_number
        else -> R.string.check_required
    })
    val fallback = context.getString(when (error.status) {
        401 -> R.string.session_expired
        403 -> R.string.permission_error
        404 -> R.string.not_found_error
        409 -> R.string.conflict_error
        413 -> R.string.file_limit_error
        429 -> R.string.rate_limit_error
        in 500..599 -> R.string.server_error
        else -> R.string.invalid_value
    })
    val arabic = context.resources.configuration.locales[0].language == "ar"
    val known = mapOf(
        "Invalid email or password." to R.string.invalid_credentials,
        "Session expired or revoked." to R.string.revoked_session,
        "Account banned." to R.string.account_banned_error,
        "Expired or invalid link." to R.string.invalid_link_error,
        "Email unavailable." to R.string.email_unavailable,
        "Unable to create this account. Try account recovery." to R.string.account_recovery_error,
        "Accept the current terms and privacy policy." to R.string.accept_policy_error,
        "Use an IANA time-zone name." to R.string.zone_error,
        "Use a valid date and time with a UTC offset." to R.string.offset_error,
        "Use local HH:MM times." to R.string.hours_error,
        "A range must have a nonzero duration." to R.string.hours_duration_error,
        "Supply both price and currency, or neither." to R.string.price_currency_error,
        "Reconfirmation is unavailable or expired." to R.string.reconfirm_error,
        "New start must be in the future." to R.string.future_start_error,
        "No future occurrences are available." to R.string.no_occurrences_error,
        "Registration is closed for this series." to R.string.series_closed_error,
        "Removal reason is required." to R.string.removal_reason_error,
        "Archived registrations are read-only." to R.string.archive_registration_error,
        "Archived registrations are read-only for organizers." to R.string.archive_registration_organizer_error,
        "Archived events are read-only for organizers." to R.string.archive_event_error,
        "Archived occurrences cannot be cancelled." to R.string.archive_cancel_error,
        "Archived or cancelled occurrences cannot be rescheduled." to R.string.archive_reschedule_error,
        "Choose a published service venue." to R.string.published_venue_error,
        "Event country/city must match its service venue." to R.string.venue_location_error,
        "Do not repeat an attachment." to R.string.duplicate_attachment_error,
        "Attachment type does not match its field." to R.string.attachment_type_error,
        "Use occurrence rescheduling to change a published schedule." to R.string.use_reschedule_error,
        "Remove registrations before lowering capacity below occupied seats." to R.string.capacity_error,
        "Cannot submit a past event." to R.string.past_event_error,
        "Organizer role required, including for moderators and administrators." to R.string.organizer_required_error,
        "This item is hidden, deleted or currently locked for review." to R.string.locked_item_error,
        "Restore the item before editing." to R.string.restore_first_error,
        "Only your own items can be changed." to R.string.own_item_error,
        "Only your own registration can be cancelled." to R.string.own_registration_error,
        "This field is required." to R.string.check_required,
        "This field may not be blank." to R.string.check_required,
        "This field may not be null." to R.string.check_required,
        "Enter a valid email address." to R.string.invalid_email,
        "Incorrect password." to R.string.incorrect_password,
        "A verified email is required to register." to R.string.verify_before_register,
        "Registration is closed." to R.string.registration_closed,
        "Cancellation cutoff has passed." to R.string.cancellation_closed,
        "Reconfirmation deadline has passed." to R.string.reconfirmation_closed,
        "Invalid credentials." to R.string.incorrect_credentials
    )
    fun message(value: String): String {
        known[value]?.let { return context.getString(it) }
        val length = Regex("(?:Minimum length is |Ensure this field has at least )([0-9]+)(?:\\.| characters.*)").matchEntire(value)
        if(length != null) return context.getString(R.string.minimum_length_error, length.groupValues[1])
        val maxLength = Regex("(?:Maximum length is |Ensure this field has no more than )([0-9]+)(?:\\.| characters.*)").matchEntire(value)
        if(maxLength != null) return context.getString(R.string.maximum_length_error, maxLength.groupValues[1])
        return if (!arabic || value.any { it in '\u0600'..'\u06ff' }) value else fallback
    }
    fun flatten(value: Any?, field: String = ""): List<String> = when (value) {
        is JSONObject -> value.keys().asSequence().toList().flatMap { key -> flatten(value.opt(key), key) }
        is JSONArray -> (0 until value.length()).flatMap { flatten(value.opt(it), field) }
        is String -> {
            val id = if (field.matches(Regex("[a-z_]+"))) context.resources.getIdentifier(field, "string", context.packageName) else 0
            listOf((if (id != 0) context.getString(id) + ": " else "") + if(field == "reason") value else message(value))
        }
        else -> emptyList()
    }
    val parsed = runCatching { JSONTokener(error.detail).nextValue() }.getOrNull()
    return if (parsed is JSONObject || parsed is JSONArray) flatten(parsed).distinct().take(8).joinToString("\n").ifBlank { fallback }
        else fallback
}

@Composable fun DateTimeEntry(caption: String, value: String, zone: String, onChange: (String) -> Unit) {
    val context = LocalContext.current
    Column {
        OutlinedTextField(value, onChange, label = { Text(caption) }, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
            supportingText = { Text(label("date_hint")) })
        OutlinedButton(onClick = {
            val selectedZone = runCatching { ZoneId.of(zone) }.getOrDefault(ZoneId.systemDefault())
            val normalized = normalizedInput(value).replace(' ', 'T')
            val initial = runCatching { OffsetDateTime.parse(normalized).atZoneSameInstant(selectedZone).toLocalDateTime() }
                .getOrElse { runCatching { LocalDateTime.parse(normalized) }.getOrDefault(LocalDateTime.now(selectedZone)) }
            android.app.DatePickerDialog(context, { _, year, month, day ->
                android.app.TimePickerDialog(context, { _, hour, minute ->
                    onChange(LocalDateTime.of(year, month + 1, day, hour, minute).toString())
                }, initial.hour, initial.minute, android.text.format.DateFormat.is24HourFormat(context)).show()
            }, initial.year, initial.monthValue - 1, initial.dayOfMonth).show()
        }) { Text(label("choose_date_time")) }
    }
}

@Composable fun TimeEntry(caption: String, value: String, onChange: (String) -> Unit) {
    val context = LocalContext.current
    Column {
        OutlinedTextField(value, onChange, label = { Text(caption) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
            supportingText = { Text(label("time_hint")) })
        OutlinedButton(onClick = {
            val time = runCatching { java.time.LocalTime.parse(normalizedInput(value)) }.getOrDefault(java.time.LocalTime.of(9, 0))
            android.app.TimePickerDialog(context, { _, hour, minute ->
                onChange(java.time.LocalTime.of(hour, minute).toString())
            }, time.hour, time.minute, android.text.format.DateFormat.is24HourFormat(context)).show()
        }) { Text(label("choose_time")) }
    }
}
