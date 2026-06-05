import polars as pl
from sklearn.linear_model import LinearRegression
from tracking.models import MeasurementSession, WeightMeasurement, PhysicalActivityLog, FoodLog, DailyActivityLog
from django.utils import timezone

def generate_insights(user):
    """
    Recopila todos los datos históricos del usuario, los cruza por fecha y 
    utiliza Machine Learning (Regresión Lineal Simple y Correlaciones)
    para generar insights de salud y control calórico.
    """
    # 1. Obtener datos crudos
    activities = PhysicalActivityLog.objects.filter(user=user).values('date', 'duration_minutes', 'not_tracked_by_watch', 'estimated_calories')
    
    foods_qs = FoodLog.objects.filter(user=user).prefetch_related('items__food', 'items__recipe__ingredients__food')
    foods_data = []
    for f in foods_qs:
        foods_data.append({
            'date': f.date,
            'eaten_out': f.eaten_out,
            'total_calories': f.get_total_calories()
        })
        
    weights = WeightMeasurement.objects.filter(user=user).values('date', 'weight')
    sessions = MeasurementSession.objects.filter(user=user).values('date', 'avg_systolic')
    
    # Datos diarios del Apple Watch
    daily_activities = DailyActivityLog.objects.filter(user=user).values('date', 'active_calories', 'resting_calories', 'steps', 'distance_km')

    # Si no hay suficientes datos básicos, salir.
    if not (activities.exists() or foods_data or weights.exists() or sessions.exists() or daily_activities.exists()):
        return {"insights": [], "scatter_data": [], "trendline_data": []}

    # 2. Convertir a Polars y agrupar por día
    df_act = pl.DataFrame(list(activities))
    if df_act.height > 0:
        # Sumar duración total de deporte y separar calorías extras no registradas por el reloj
        df_act = df_act.with_columns([
            pl.col('duration_minutes').fill_null(0).cast(pl.Int64),
            pl.col('estimated_calories').fill_null(0).cast(pl.Int64),
            pl.col('not_tracked_by_watch').fill_null(False).cast(pl.Boolean)
        ])
        df_act_agg = df_act.group_by('date').agg([
            pl.col('duration_minutes').sum().alias('sport_duration'),
            pl.col('estimated_calories').filter(pl.col('not_tracked_by_watch')).sum().alias('extra_exercise_calories')
        ])
    else:
        df_act_agg = pl.DataFrame(
            {"date": [], "sport_duration": [], "extra_exercise_calories": []},
            schema={"date": pl.Date, "sport_duration": pl.Int64, "extra_exercise_calories": pl.Int64}
        )

    if foods_data:
        df_food = pl.DataFrame(foods_data)
        df_food = df_food.with_columns(pl.col("eaten_out").cast(pl.Int64))
        df_food = df_food.group_by('date').agg([
            pl.col('eaten_out').sum().alias('eat_out_count'),
            pl.col('total_calories').sum().alias('daily_calories')
        ])
    else:
        df_food = pl.DataFrame({"date": [], "eat_out_count": [], "daily_calories": []}, schema={"date": pl.Date, "eat_out_count": pl.Int64, "daily_calories": pl.Float64})

    df_weight = pl.DataFrame(list(weights))
    if df_weight.height > 0:
        df_weight = df_weight.with_columns(pl.col('weight').cast(pl.Float64))
        df_weight = df_weight.group_by('date').agg(pl.col('weight').mean().alias('weight'))
    else:
        df_weight = pl.DataFrame({"date": [], "weight": []}, schema={"date": pl.Date, "weight": pl.Float64})
        
    df_session = pl.DataFrame(list(sessions))
    if df_session.height > 0:
        df_session = df_session.filter(pl.col('avg_systolic').is_not_null())
        df_session = df_session.group_by('date').agg(pl.col('avg_systolic').mean().alias('avg_sys'))
    else:
        df_session = pl.DataFrame({"date": [], "avg_sys": []}, schema={"date": pl.Date, "avg_sys": pl.Float64})

    df_daily = pl.DataFrame(list(daily_activities))
    if df_daily.height > 0:
        df_daily = df_daily.with_columns([
            pl.col('active_calories').cast(pl.Int64),
            pl.col('resting_calories').cast(pl.Int64),
            pl.col('steps').cast(pl.Int64),
            pl.col('distance_km').cast(pl.Float64)
        ])
        df_daily = df_daily.group_by('date').agg([
            pl.col('active_calories').mean().alias('active_calories'),
            pl.col('resting_calories').mean().alias('resting_calories'),
            pl.col('steps').sum().alias('steps'),
            pl.col('distance_km').sum().alias('distance_km')
        ])
    else:
        df_daily = pl.DataFrame(
            {"date": [], "active_calories": [], "resting_calories": [], "steps": [], "distance_km": []},
            schema={"date": pl.Date, "active_calories": pl.Int64, "resting_calories": pl.Int64, "steps": pl.Int64, "distance_km": pl.Float64}
        )

    # 3. Unir todo
    dates_frames = [df for df in [df_act_agg, df_food, df_weight, df_session, df_daily] if df.height > 0]
    if not dates_frames:
        return {"insights": [], "scatter_data": []}
    
    all_dates = pl.DataFrame()
    for df in dates_frames:
        all_dates = pl.concat([all_dates, df.select('date')])
    all_dates = all_dates.unique().sort('date')
    
    df_master = all_dates
    for df in dates_frames:
        df_master = df_master.join(df, on='date', how='left')

    # Asegurarse de que todas las columnas necesarias existan en df_master (evita ColumnNotFoundError en bases de datos vacías)
    
    # 1. Deporte y Ejercicio Extra
    if 'sport_duration' in df_master.columns:
        df_master = df_master.with_columns(pl.col('sport_duration').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).cast(pl.Int64).alias('sport_duration'))
        
    if 'extra_exercise_calories' in df_master.columns:
        df_master = df_master.with_columns(pl.col('extra_exercise_calories').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).cast(pl.Int64).alias('extra_exercise_calories'))
        
    # 2. Comidas y Restaurantes
    if 'eat_out_count' in df_master.columns:
        df_master = df_master.with_columns(pl.col('eat_out_count').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).cast(pl.Int64).alias('eat_out_count'))
        
    if 'daily_calories' in df_master.columns:
        df_master = df_master.with_columns(pl.col('daily_calories').fill_null(0.0))
    else:
        df_master = df_master.with_columns(pl.lit(0.0).cast(pl.Float64).alias('daily_calories'))
        
    # 3. Actividad Watch
    if 'active_calories' in df_master.columns:
        df_master = df_master.with_columns(pl.col('active_calories').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).cast(pl.Int64).alias('active_calories'))
        
    if 'steps' in df_master.columns:
        df_master = df_master.with_columns(pl.col('steps').fill_null(0))
    else:
        df_master = df_master.with_columns(pl.lit(0).cast(pl.Int64).alias('steps'))
        
    if 'distance_km' in df_master.columns:
        df_master = df_master.with_columns(pl.col('distance_km').fill_null(0.0))
    else:
        df_master = df_master.with_columns(pl.lit(0.0).cast(pl.Float64).alias('distance_km'))

    # 4. Peso y Tensión (forward fill)
    if 'weight' in df_master.columns:
        df_master = df_master.with_columns(pl.col('weight').forward_fill())
    else:
        df_master = df_master.with_columns(pl.lit(None).cast(pl.Float64).alias('weight'))
        
    if 'avg_sys' in df_master.columns:
        df_master = df_master.with_columns(pl.col('avg_sys').forward_fill())
    else:
        df_master = df_master.with_columns(pl.lit(None).cast(pl.Float64).alias('avg_sys'))

    # 5. Calorías en reposo (Watch BMR o fallback)
    user_height = user.height_cm
    user_gender = user.gender
    user_birth = user.birth_date
    age = 35
    if user_birth:
        from datetime import date
        today = date.today()
        age = today.year - user_birth.year - ((today.month, today.day) < (user_birth.month, user_birth.day))

    fallback_bmr = 1800 if user_gender == "male" else 1400
    
    if 'resting_calories' in df_master.columns:
        if user_height and user_birth and user_gender:
            constant = 5 if user_gender == "male" else -161
            df_master = df_master.with_columns(
                pl.col('resting_calories').fill_null(
                    10.0 * pl.col('weight').fill_null(70.0) + (6.25 * user_height - 5.0 * age + constant)
                )
            )
        else:
            df_master = df_master.with_columns(
                pl.col('resting_calories').fill_null(fallback_bmr)
            )
    else:
        if user_height and user_birth and user_gender:
            constant = 5 if user_gender == "male" else -161
            df_master = df_master.with_columns(
                (10.0 * pl.col('weight').fill_null(70.0) + (6.25 * user_height - 5.0 * age + constant)).alias('resting_calories')
            )
        else:
            df_master = df_master.with_columns(
                pl.lit(fallback_bmr).cast(pl.Float64).alias('resting_calories')
            )

    # Calcular Gasto Total y Balance Calórico
    df_master = df_master.with_columns(
        (pl.col('resting_calories') + pl.col('active_calories') + pl.col('extra_exercise_calories')).alias('total_expenditure')
    )
    df_master = df_master.with_columns(
        (pl.col('daily_calories') - pl.col('total_expenditure')).alias('caloric_balance')
    )

    df_master = df_master.sort('date')
    
    df_master = df_master.with_columns([
        pl.col('weight').shift(-1).alias('weight_next_day'),
        pl.col('avg_sys').shift(-1).alias('sys_next_day'),
    ])
    df_master = df_master.with_columns([
        (pl.col('weight_next_day') - pl.col('weight')).alias('weight_diff_next'),
        (pl.col('sys_next_day') - pl.col('avg_sys')).alias('sys_diff_next'),
    ])

    insights = []

    # 4. Regresión Lineal de Balance Calórico frente a Peso
    df_ml_balance = df_master.drop_nulls(subset=['caloric_balance', 'weight_diff_next'])
    if df_ml_balance.height >= 7:
        X_bal = df_ml_balance.select('caloric_balance').to_numpy()
        y_bal = df_ml_balance.select('weight_diff_next').to_numpy().ravel()
        
        reg_bal = LinearRegression()
        reg_bal.fit(X_bal, y_bal)
        coef_balance = reg_bal.coef_[0]
        
        if coef_balance > 0.00001:
            gramos_por_500_kcal = coef_balance * 500 * 1000
            insights.append({
                "type": "success",
                "icon": "bi-fire",
                "title": "Impacto del Balance Calórico",
                "text": f"Nuestra IA estima que por cada 500 kcal de déficit diario acumulado, tu peso disminuye en media {gramos_por_500_kcal:.0f}g al día siguiente. Mantén el balance calórico negativo para asegurar la pérdida."
            })
        else:
            insights.append({
                "type": "success",
                "icon": "bi-arrow-down-circle",
                "title": "Control Calórico Activo",
                "text": "Has comenzado a registrar balance calórico. Mantener un balance negativo diario constante es la vía garantizada para perder peso."
            })
    else:
        # Recomendación general de balance calórico si hay pocos datos de peso
        insights.append({
            "type": "info",
            "icon": "bi-info-circle",
            "title": "Control calórico activado",
            "text": "Sigue registrando tus calorías ingeridas (comidas) y quemadas (Apple Watch y Karate) para que la IA personalice tus tasas metabólicas reales."
        })

    # 5. Regresión Lineal para Deporte
    df_ml_weight = df_master.drop_nulls(subset=['sport_duration', 'daily_calories', 'weight_diff_next'])
    if df_ml_weight.height >= 10:
        X = df_ml_weight.select(['sport_duration', 'daily_calories']).to_numpy()
        y = df_ml_weight.select('weight_diff_next').to_numpy().ravel()
        
        reg_weight = LinearRegression()
        reg_weight.fit(X, y)
        coef_sport = reg_weight.coef_[0]
        
        if coef_sport < -0.001:
            gramos_por_30_min = abs(coef_sport * 30 * 1000)
            insights.append({
                "type": "success",
                "icon": "bi-lightning-charge",
                "title": "Impacto del Deporte",
                "text": f"Por cada 30 minutos de deporte diario (incluyendo Karate estimado), tu peso disminuye en media {gramos_por_30_min:.0f}g al día siguiente."
            })

    # 6. Alerta de comidas fuera
    df_ml_sys = df_master.drop_nulls(subset=['sport_duration', 'eat_out_count', 'sys_diff_next'])
    if df_ml_sys.height >= 10:
        X = df_ml_sys.select(['sport_duration', 'eat_out_count']).to_numpy()
        y = df_ml_sys.select('sys_diff_next').to_numpy().ravel()
        
        reg_sys = LinearRegression()
        reg_sys.fit(X, y)
        sys_food_coef = reg_sys.coef_[1]

        if sys_food_coef > 1.0:
            insights.append({
                "type": "danger",
                "icon": "bi-heart-pulse",
                "title": "Alerta de Sodio / Comidas Fuera",
                "text": f"Comer fuera de casa está aumentando tu presión sistólica media en +{sys_food_coef:.1f} mmHg. ¡Vigila el exceso de sal en restaurantes!"
            })

    # 7. Consejo Predictivo Personalizado para Peso (Consejo diario)
    target_weekly_loss = float(user.target_weekly_loss_kg or 0.5)
    # 1 kg de grasa = ~7700 kcal. Déficit diario requerido = (target_weekly_loss * 7700) / 7
    required_daily_deficit = (target_weekly_loss * 7700.0) / 7.0
    
    # Obtener el último día registrado para aconsejar
    last_day_data = df_master.tail(1)
    if last_day_data.height > 0:
        last_row = last_day_data.iter_rows(named=True).__next__()
        last_intake = last_row['daily_calories']
        last_exp = last_row['total_expenditure']
        last_bal = last_row['caloric_balance']
        
        # Objetivo de balance calórico diario
        target_balance = -required_daily_deficit
        
        if last_bal > target_balance:
            # Falta déficit
            extra_needed = last_bal - target_balance # kcal adicionales a quemar o dejar de comer
            # Aprox 1000 pasos = 45 kcal.
            extra_steps = (extra_needed / 45.0) * 1000.0
            
            # Karate quema aprox 8 MET. Para un peso dado, calculamos kcal/min.
            latest_w_val = last_row['weight'] if last_row['weight'] is not None else 75.0
            karate_kcal_per_min = (8.0 * latest_w_val) / 60.0
            karate_min = extra_needed / karate_kcal_per_min if karate_kcal_per_min > 0 else extra_needed / 10.0
            
            insights.append({
                "type": "warning",
                "icon": "bi-bullseye",
                "title": "Consejo de Objetivo Semanal",
                "text": f"Para mantener tu ritmo de pérdida de {target_weekly_loss} kg/semana, necesitas un déficit diario de {required_daily_deficit:.0f} kcal (balance de {target_balance:.0f} kcal). Ayer tu balance fue de {last_bal:.0f} kcal. Para compensar hoy, te aconsejamos dar {extra_steps:.0f} pasos más o entrenar Karate por {karate_min:.0f} minutos."
            })
        else:
            insights.append({
                "type": "success",
                "icon": "bi-trophy",
                "title": "¡Objetivo de Balance Superado!",
                "text": f"¡Ayer lograste un balance de {last_bal:.0f} kcal, superando tu objetivo de déficit de {required_daily_deficit:.0f} kcal! Mantén esta constancia para asegurar tu progreso."
            })

    # 8. Gráficos de línea de tiempo
    timeline_labels = []
    weight_data = []
    sport_data = []
    
    df_timeline = df_master.filter(pl.col('weight').is_not_null() | (pl.col('sport_duration') > 0))
    df_timeline = df_timeline.sort('date')
    
    for row in df_timeline.iter_rows(named=True):
        timeline_labels.append(row['date'].strftime('%Y-%m-%d'))
        weight_data.append(row['weight'] if row['weight'] is not None else None)
        sport_data.append(row['sport_duration'])

    return {
        "insights": insights,
        "timeline_labels": timeline_labels,
        "weight_data": weight_data,
        "sport_data": sport_data
    }
