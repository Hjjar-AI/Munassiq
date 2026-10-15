package org.munassiq.app.ui

/** Native fields for existing endpoints; never an editable JSON/API console. */
data class Field(val key: String, val type: String = "text", val choices: List<String> = emptyList(), val optional: Boolean = false)
data class FormSpec(val path: String, val method: String, val title: String, val fields: List<Field>, val initial: org.json.JSONObject = org.json.JSONObject())

object NativeForms {
    fun account(kind: String) = when (kind) {
        "signup" -> FormSpec("auth/signup/", "POST", "signup", listOf(Field("name"), Field("email"), Field("password", "password"), Field("language", "choice", listOf("ar", "en")), Field("consent", "boolean")))
        "forgot" -> FormSpec("auth/password/forgot/", "POST", "forgot", listOf(Field("email")))
        "verify" -> FormSpec("auth/verification/request/", "POST", "verify", listOf(Field("email")))
        "profile" -> FormSpec("me/", "PATCH", "profile", listOf(Field("name"), Field("language", "choice", listOf("ar", "en"))))
        "password" -> FormSpec("me/password/change/", "POST", "password", listOf(Field("current_password", "password"), Field("password", "password")))
        "email" -> FormSpec("me/email/change/", "POST", "email", listOf(Field("email"), Field("password", "password")))
        "delete_account" -> FormSpec("me/", "DELETE", "delete_account", listOf(Field("password", "password"), Field("confirm", "boolean")))
        "feedback" -> FormSpec("feedback/", "POST", "feedback", listOf(Field("text", "long")))
        "apply" -> FormSpec("organizer-requests/", "POST", "apply", listOf(Field("name"),Field("workplace"),Field("reason","long"),Field("credential","credential")))
        "organizer_profile" -> FormSpec("me/organizer-profile/","PATCH","organizer_profile",listOf(Field("bio","long",optional=true),Field("photo_id","image",optional=true)))
        else -> FormSpec("me/notification-preferences/", "PATCH", "preferences", listOf(Field("language","choice",listOf("ar","en")),Field("time_zone"), Field("reminders","boolean"),Field("announcements","boolean"),Field("followed_events","boolean"),Field("follow_delivery","choice",listOf("instant","daily")),Field("quiet_start",optional=true),Field("quiet_end",optional=true)))
    }
    fun content(kind: String, id: Long? = null, initial: org.json.JSONObject = org.json.JSONObject()): FormSpec {
        val common = listOf(Field("description","long"),Field("country_id","countries"),Field("city_id","cities",optional=kind=="event"),Field("category_ids","categories"),Field("time_zone"),Field("latitude","number",optional=kind=="event"),Field("longitude","number",optional=kind=="event"),Field("contact_person",optional=true),Field("contact_scope","choice",listOf("personal","organization")),Field("phone",optional=true),Field("image_ids","images",optional=true))
        val specific = if(kind=="event") listOf(Field("title"),Field("speaker_name"),Field("topic"),Field("mode","choice",listOf("in_person","online","both")),Field("online_url",optional=true),Field("registration_contact",optional=true),Field("registration_url",optional=true),Field("address",optional=true),Field("service_id","services",optional=true),Field("starts_at","date"),Field("duration_minutes","number"),Field("seat_limit","number"),Field("registration_deadline","date",optional=true),Field("cancellation_cutoff_minutes","number"),Field("recurrence","choice",listOf("none","weekly","monthly")),Field("occurrence_count","number"),Field("pdf_id","pdf",optional=true))
        else listOf(Field("name"),Field("type","choice",listOf("clinic","center","contact_office","service_at_place")),Field("address"),Field("hours","hours",optional=true),Field("price","number",optional=true),Field("currency_id","currencies",optional=true))
        return FormSpec("${kind}s/"+(id?.let{"$it/"}?:""),if(id==null)"POST" else "PATCH",if(kind=="event")"edit_event" else "edit_service",specific+common,initial)
    }
}
